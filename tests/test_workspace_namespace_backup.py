"""The full-root SQLite recovery image includes every customer CRM file."""
import hashlib
import shutil
import pytest
from offsetx_apollo_builder.outreach.backup import (
    create_encrypted_backup, restore_encrypted_backup, discard_restore_safety,
    validate_encrypted_backup,
)
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore


@pytest.mark.crm_sqlite_only("Exercises full-root SQLite CRM files; PostgreSQL multi-schema recovery is covered separately")
def test_full_root_restores_two_private_crm_files_with_equal_emails(tmp_path):
    data = tmp_path / 'source'
    database = data / 'outreach.db'
    with OutreachStore(database) as admin:
        admin.initialize()
    paths = {}
    for workspace in ('alpha', 'beta'):
        relative = 'crm_workspaces/' + hashlib.sha256(workspace.encode()).hexdigest()[:32] + '/crm.db'
        paths[workspace] = relative
        engine = OutreachEngine(data / relative, workspace_id=workspace)
        try:
            campaign = engine.create_campaign(name='PRIVATE ' + workspace)
            engine.store.create_manual_campaign_contact(campaign, ContactInput(
                full_name='Anita Rao', email='same@example.com', company='Example Exports', category='CBAM'))
            engine.email_expert.memory.add_manual(content='PRIVATE '+workspace+' evidence')
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
            finally:
                engine.close()
    finally:
        discard_restore_safety(result)
