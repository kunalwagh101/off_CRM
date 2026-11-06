"""Drafts reach configured Connectors through the existing broker, never a raw client."""
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

TOKEN = 'draft-connectors-owner-' + 'x' * 40
HEADERS = {'X-Offsetx-Token': TOKEN}
CONTACTS = b'''Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension
Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff
'''


def test_actual_draft_generation_uses_workspace_broker_without_legacy_profiles(tmp_path):
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path / 'crm.db',
        data_dir=tmp_path / 'data', export_dir=tmp_path / 'exports', frontend_dist=tmp_path / 'missing',
        api_token=TOKEN, allowed_hosts=('testserver',)))
    with TestClient(app, headers=HEADERS) as client:
        campaign = client.post('/api/v1/campaigns', json={'name': 'Connector drafts'}).json()['id']
        imported = client.post(f'/api/v1/campaigns/{campaign}/contacts/import',
                               files={'file': ('contacts.csv', CONTACTS, 'text/csv')})
        assert imported.status_code == 200, imported.text
        # With the real unconfigured broker, refuse before creating any draft.
        refused = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate',
                              json={'use_connectors': True, 'stages': ['initial']})
        assert refused.status_code in (400, 403, 409, 422), refused.text
        assert client.get(f'/api/v1/campaigns/{campaign}/drafts').json()['total'] == 0
        for selection in ({'provider_profile_ids': ['old-profile']},
                          {'use_provider_fallback': True, 'fallback_strategy': 'parallel'}):
            rejected = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate', json=selection)
            assert rejected.status_code == 409 and 'Connectors' in rejected.text
        local = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate', json={'stages': ['initial']})
        assert local.status_code == 200 and local.json()['generated'] == 1, local.text
        requests = []
        class Broker:
            def with_credential_resolver(self, resolver):
                return self
            def plan(self, request, settings, **kwargs):
                return [object()], []
            def call(self, request, settings, **kwargs):
                requests.append((request, settings.workspace_id))
                blueprint = json.loads(request.template_text)
                return SimpleNamespace(text=json.dumps({'subject': blueprint['subject'], 'body': blueprint['body']}),
                    provider_id='test-connector', provider_name='Test connector', model_id='test-model', policy='standard', log_id='test-log')
        app.state.ai_broker = Broker()
        def legacy_must_not_run(**kwargs):
            raise AssertionError('Legacy profile router must not see this request')
        app.state.provider_profiles.router = legacy_must_not_run
        response = client.post(f'/api/v1/campaigns/{campaign}/drafts/generate',
                               json={'use_connectors': True, 'stages': ['initial']})
        assert response.status_code == 200, response.text
        assert response.json()['generated'] == 1, response.text
        assert response.json()['failures'] == []
        assert len(requests) == 1 and requests[0][1] == 'local'
        request = requests[0][0]
        assert request.task_type == 'draft_email' and request.data_class.value == 'campaign'
        assert request.person.full_name == 'Anita Rao' and not hasattr(request.person, 'email')
        assert 'anita@example.com' not in request.template_text + request.campaign_notes + request.instructions
        assert not request.conversation and not request.unrestricted


def provider_for(result_text):
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftProvider
    from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
    class Broker:
        def call(self, request, settings, *, system_prompt, expect_json=False):
            return SimpleNamespace(text=result_text, provider_id='test', model_id='test', policy='standard', log_id='test')
    return ConnectorDraftProvider(Broker(), WorkspaceEgressSettings())


def test_identity_restoration_does_not_rewrite_a_literal_token_in_a_name():
    provider = provider_for(json.dumps({'subject': 'PERSON_1', 'body': 'Hello PERSON_1'}))
    result = json.loads(provider.generate(system_prompt='trusted code', user_prompt=json.dumps({
        'recipient': {'full_name': 'COMPANY_1', 'company': 'A real company'}, 'template_blueprint': {}
    })))
    assert result['subject'] == 'COMPANY_1'


def test_identity_restoration_cannot_expand_a_small_result_without_a_bound():
    import pytest
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftError
    provider = provider_for(json.dumps({'subject': 'Hello', 'body': 'COMPANY_1'}))
    with pytest.raises(ConnectorDraftError):
        provider.generate(system_prompt='trusted code', user_prompt=json.dumps({
            'recipient': {'company': 'X' * 10000}, 'template_blueprint': {}
        }))


def test_unknown_recipient_tokens_fail_instead_of_becoming_a_different_name():
    import pytest
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftError
    provider = provider_for(json.dumps({'subject': 'PERSON_10', 'body': 'Hello'}))
    with pytest.raises(ConnectorDraftError):
        provider.generate(system_prompt='trusted code', user_prompt=json.dumps({
            'recipient': {'full_name': 'Anita'}, 'template_blueprint': {}
        }))


def test_connector_payload_obeys_the_existing_policy_boundary():
    from offsetx_apollo_builder.ai.payload import build_payload
    from offsetx_apollo_builder.ai.tiers import DataPolicy
    from offsetx_apollo_builder.outreach.email_expert import OFFSETX_SIGNATURE
    provider = provider_for(json.dumps({'subject': 'Hello', 'body': 'A question?'}))
    requests = []
    original = provider.broker.call
    def capture(request, settings, **kwargs):
        requests.append(request)
        return original(request, settings, **kwargs)
    provider.broker.call = capture
    provider.generate(system_prompt='private system material must not leave', user_prompt=json.dumps({
        'recipient': {'full_name': 'Anita Rao', 'company': 'Example Exports', 'email': 'anita@example.com',
                      'private_new_column': 'private CRM content'},
        'template_blueprint': {'subject': 'Anita Rao', 'body': 'A question?\n\n' + OFFSETX_SIGNATURE},
        'retrieved_guidance': 'Approved campaign guidance', 'approved_memory': 'Approved campaign memory',
        'hard_rules': {'signature': OFFSETX_SIGNATURE, 'private_rule': 'private rule text'}
    }))
    strict = build_payload(requests[0], DataPolicy.STRICT)
    assert 'template' not in strict and 'campaign_notes' not in strict
    strict_text = json.dumps(strict)
    assert 'Anita Rao' not in strict_text and 'Example Exports' not in strict_text
    standard = build_payload(requests[0], DataPolicy.STANDARD)
    assert 'template' in standard and 'campaign_notes' in standard
    text = json.dumps(standard)
    for private in ('anita@example.com', 'private CRM content', 'private system material', 'private rule text', OFFSETX_SIGNATURE):
        assert private not in text


def test_invalid_connector_output_never_leaves_stale_success_provenance(tmp_path):
    import pytest
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftError
    provider = provider_for(json.dumps({'subject': 'Hello', 'body': 'A question?'}))
    provider.data_dir = tmp_path
    offered = json.dumps({'recipient': {'full_name': 'Anita'}, 'template_blueprint': {}})
    provider.generate(system_prompt='', user_prompt=offered)
    assert provider.last_run['provider_id'] == 'test'
    for invalid in ('not json', '{}', '{"subject":1,"body":"test"}',
                    json.dumps({'subject': '', 'body': 'A'}),
                    json.dumps({'subject': 'A', 'body': 'B' * 8001}),
                    json.dumps({'subject': 'A', 'body': 'B', 'tool_call': 'execute'})):
        provider.broker.call = lambda *args, **kwargs: SimpleNamespace(text=invalid)
        with pytest.raises(ConnectorDraftError, match='Reference: E-'):
            provider.generate(system_prompt='', user_prompt=offered)
        assert provider.last_run['status'] == 'failed'
        assert 'provider_id' not in provider.last_run


def test_provider_failure_is_secret_safe_for_user_and_logs(tmp_path, capsys):
    import pytest
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftError
    provider = provider_for('unused')
    provider.data_dir = tmp_path
    def fail(*args, **kwargs):
        raise RuntimeError('sk-live-secret-content and PRIVATE CUSTOMER MESSAGE')
    provider.broker.call = fail
    with pytest.raises(ConnectorDraftError) as failure:
        provider.generate(system_prompt='', user_prompt='{}')
    visible = str(failure.value) + capsys.readouterr().out
    assert 'sk-live-secret-content' not in visible and 'PRIVATE CUSTOMER MESSAGE' not in visible
    assert 'Open Connectors' in visible and 'Reference: E-' in visible


def test_actual_broker_transports_and_logs_a_connector_draft(tmp_path):
    from offsetx_apollo_builder.ai import EgressBroker, EgressLog, ProviderRegistry, WorkspaceEgressSettings
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftProvider
    log = EgressLog(tmp_path / 'egress.db')
    broker = EgressBroker(registry=ProviderRegistry(Path('config/providers.yaml')),
                          credential_resolver=lambda _: 'test-key', logger=log.record)
    sent = []
    class Transport:
        def generate(self, *, system_prompt, user_prompt):
            sent.append((system_prompt, json.loads(user_prompt)))
            return json.dumps({'subject': 'Supplier evidence', 'body': 'Could this help? Remain factual.'})
    broker._instantiate = lambda _: Transport()
    provider = ConnectorDraftProvider(broker, WorkspaceEgressSettings(enabled_provider_ids=('mistral',)), data_dir=tmp_path)
    provider.preflight()
    result = json.loads(provider.generate(system_prompt='PRIVATE SYSTEM MUST NOT LEAVE', user_prompt=json.dumps({
        'recipient': {'full_name': 'Anita', 'email': 'anita@example.com'},
        'stage': 'initial', 'template_blueprint': {'subject': 'Supplier evidence', 'body': 'Could this help?'}
    })))
    assert result['subject'] == 'Supplier evidence'
    assert len(sent) == 1
    assert 'PRIVATE SYSTEM' not in sent[0][0]
    assert 'anita@example.com' not in json.dumps(sent)
    assert 'template' in sent[0][1] and 'initial' in sent[0][1]['campaign_notes']
    assert provider.last_run['log_id'] and provider.last_run['attempts']


def test_drafts_refuse_policy_without_required_template_context_before_transport(tmp_path):
    import pytest
    from offsetx_apollo_builder.ai import EgressBroker, ProviderRegistry, WorkspaceEgressSettings, DataPolicy, NoPermittedProvider
    from offsetx_apollo_builder.ai.draft_provider import ConnectorDraftProvider
    broker = EgressBroker(registry=ProviderRegistry(Path('config/providers.yaml')), credential_resolver=lambda _: 'test-key')
    provider = ConnectorDraftProvider(broker, WorkspaceEgressSettings(enabled_provider_ids=('mistral',),
        default_policy_by_provider={'mistral': DataPolicy.STRICT}), data_dir=tmp_path)
    with pytest.raises(NoPermittedProvider, match='policy|Policy|permitted'):
        provider.preflight()


def test_connector_provenance_retains_safe_failed_then_successful_attempts():
    provider = provider_for('unused')
    provider.broker.call = lambda *args, **kwargs: SimpleNamespace(
        text='{"subject":"Hello","body":"A factual question?"}', provider_id='second',
        model_id='model2', policy='standard', log_id='log2', attempts=[
            {'provider_id': 'first', 'model_id': 'model1', 'status': 'failed',
             'failure_kind': 'rate_limited', 'detail': 'PRIVATE PROVIDER RESPONSE'},
            {'provider_id': 'second', 'model_id': 'model2', 'status': 'used'}])
    provider.generate(system_prompt='', user_prompt='{}')
    assert [attempt['provider_id'] for attempt in provider.last_run['attempts']] == ['first', 'second']
    assert 'PRIVATE' not in json.dumps(provider.last_run)
