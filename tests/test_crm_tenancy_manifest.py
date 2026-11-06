"""Legacy ownership must be explicit, complete, consistent and read-only."""
import copy
import pytest
from offsetx_apollo_builder.outreach.tenancy import OwnershipError, validate_ownership


def manifest(**tables):
    return {'version': 1, 'assignments': tables}


def assignment(identifier, workspace):
    return {'key': [identifier], 'workspace_id': workspace}


def test_legacy_records_are_never_automatically_assigned_to_local():
    rows = {'campaigns': [{'id': 'campaign'}]}
    with pytest.raises(OwnershipError, match='explicit'):
        validate_ownership(rows, manifest(), workspaces={'local', 'alpha'})
    assert rows == {'campaigns': [{'id': 'campaign'}]}


def test_explicit_assignments_preserve_existing_owners_and_input():
    rows = {'campaigns': [{'id': 'campaign'}], 'contacts': [{'id': 'person'}],
            'campaign_contacts': [{'id': 'member', 'campaign_id': 'campaign', 'contact_id': 'person'}],
            'memory_items': [{'id': 'memory', 'workspace_id': 'beta'}]}
    original = copy.deepcopy(rows)
    plan = validate_ownership(rows, manifest(campaigns=[assignment('campaign', 'alpha')],
        contacts=[assignment('person', 'alpha')]), workspaces={'local', 'alpha', 'beta'})
    assert plan.owner('campaign_contacts', ('member',)) == 'alpha'
    assert plan.owner('memory_items', ('memory',)) == 'beta'
    assert rows == original


def test_contact_shared_between_differently_assigned_campaigns_is_refused():
    rows = {'campaigns': [{'id': 'a'}, {'id': 'b'}], 'contacts': [{'id': 'person'}],
            'campaign_contacts': [{'id': 'one', 'campaign_id': 'a', 'contact_id': 'person'},
                                  {'id': 'two', 'campaign_id': 'b', 'contact_id': 'person'}]}
    with pytest.raises(OwnershipError, match='crosses workspace'):
        validate_ownership(rows, manifest(campaigns=[assignment('a', 'alpha'), assignment('b', 'beta')],
            contacts=[assignment('person', 'alpha')]), workspaces={'local', 'alpha', 'beta'})


@pytest.mark.parametrize('bad', [
    {'version': True, 'assignments': {}},
    {'version': 1, 'assignments': {}, 'default_workspace': 'local'},
    manifest(campaigns=[assignment('missing', 'alpha')]),
    manifest(campaigns=[assignment('campaign', 'unknown')]),
    manifest(campaigns=[assignment('campaign', 'alpha'), assignment('campaign', 'alpha')]),
])
def test_invalid_or_ambiguous_manifests_are_refused(bad):
    with pytest.raises(OwnershipError):
        validate_ownership({'campaigns': [{'id': 'campaign'}]}, bad, workspaces={'local', 'alpha'})


def test_existing_recorded_workspace_cannot_be_reassigned():
    with pytest.raises(OwnershipError, match='recorded owner'):
        validate_ownership({'campaigns': [{'id': 'campaign', 'workspace_id': 'beta'}]},
            manifest(campaigns=[assignment('campaign', 'alpha')]), workspaces={'local', 'alpha', 'beta'})


def test_task_cannot_reference_a_membership_from_another_campaign():
    rows = {'campaigns': [{'id': 'a', 'workspace_id': 'alpha'}, {'id': 'b', 'workspace_id': 'beta'}],
            'contacts': [{'id': 'p', 'workspace_id': 'beta'}],
            'campaign_contacts': [{'id': 'member', 'campaign_id': 'b', 'contact_id': 'p'}],
            'campaign_followup_tasks': [{'id': 'task', 'campaign_id': 'a', 'campaign_contact_id': 'member'}]}
    with pytest.raises(OwnershipError, match='crosses workspace'):
        validate_ownership(rows, manifest(), workspaces={'alpha', 'beta'})


def test_a_draft_cannot_use_a_template_owned_by_another_workspace():
    rows = {'campaigns': [{'id': 'campaign', 'workspace_id': 'alpha'}],
            'contacts': [{'id': 'person', 'workspace_id': 'alpha'}],
            'campaign_contacts': [{'id': 'member', 'campaign_id': 'campaign', 'contact_id': 'person'}],
            'email_templates': [{'id': 'template', 'workspace_id': 'beta'}],
            'drafts': [{'id': 'draft', 'campaign_contact_id': 'member', 'template_id': 'template'}]}
    with pytest.raises(OwnershipError, match='crosses workspace'):
        validate_ownership(rows, manifest(), workspaces={'alpha', 'beta'})


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_actual_snapshot_is_read_only_stable_and_detects_data_changes(tmp_path, request, backend):
    from offsetx_apollo_builder.outreach.store import OutreachStore
    from offsetx_apollo_builder.outreach.tenancy import capture_legacy_snapshot
    target = str(tmp_path / 'crm.db') if backend == 'sqlite' else request.getfixturevalue('isolated_postgres_target')
    store = OutreachStore(target)
    store.initialize()
    try:
        campaign = store.create_campaign(name='Private company material', daily_send_limit=5)
        before = store.table_counts()
        snapshot = capture_legacy_snapshot(store)
        choices = manifest(campaigns=[assignment(campaign, 'alpha')])
        first = validate_ownership(snapshot, choices, workspaces={'alpha'})
        assert first.counts['campaigns'] == 1
        assert store.table_counts() == before
        assert first.source_sha256 == validate_ownership(capture_legacy_snapshot(store), choices, workspaces={'alpha'}).source_sha256
        store.update_campaign(campaign, {'name': 'Changed material'})
        assert first.source_sha256 != validate_ownership(capture_legacy_snapshot(store), choices, workspaces={'alpha'}).source_sha256
    finally:
        store.close()


def test_unsubscribe_cannot_become_an_install_wide_reputation_suppression():
    rows = {'email_suppressions': [{'email': 'private@example.com', 'reason': 'unsubscribe'}]}
    with pytest.raises(OwnershipError, match='suppression'):
        validate_ownership(rows, manifest(email_suppressions=[assignment('private@example.com', '__install__')]), workspaces={'alpha'})


def test_required_delivery_reference_cannot_be_empty():
    rows = {'campaigns': [{'id': 'campaign', 'workspace_id': 'alpha'}],
            'contacts': [{'id': 'person', 'workspace_id': 'alpha'}],
            'campaign_contacts': [{'id': 'member', 'campaign_id': 'campaign', 'contact_id': 'person'}],
            'email_send_jobs': [{'id': 'job', 'campaign_id': 'campaign', 'campaign_contact_id': 'member', 'draft_id': ''}]}
    with pytest.raises(OwnershipError, match='required reference'):
        validate_ownership(rows, manifest(), workspaces={'alpha'})


def test_explicit_reputation_scope_is_preserved_and_never_assumed():
    rows = {'email_suppressions': [{'email': 'private@example.com', 'reason': 'hard_bounce'}]}
    with pytest.raises(OwnershipError, match='explicit'):
        validate_ownership(rows, manifest(), workspaces={'alpha'})
    plan = validate_ownership(rows, manifest(email_suppressions=[assignment('private@example.com', '__install__')]), workspaces={'alpha'})
    assert plan.owner('email_suppressions', ('private@example.com',)) == '__install__'
