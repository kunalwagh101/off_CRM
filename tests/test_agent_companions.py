"""S-04.01.01: companion grants are enforced by the run host."""
import asyncio

from offsetx_apollo_builder.agent import AgentRun, Companion
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.browser.trace import Trace
from test_agent_run import _Broker, _Page


def test_model_cannot_execute_a_verb_outside_companion_grants(tmp_path):
    broker = _Broker(['{"state":"act","action":"click","args":{"handle":1}}'])
    page = _Page()
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(
        enabled_provider_ids=('trusted',)), page=page, trace=Trace.open(tmp_path))
    profile = dict(id='scout', name='Scout', workspace_id='local', instructions='Read only',
                   tools=('read',), memory_scopes=())
    run.companion = Companion(**profile)
    outcome = asyncio.run(run.run('Inspect public leads', step_budget=1))
    assert outcome.status == 'refused'
    assert page.actions == []
    assert 'grant' in outcome.message.lower()


import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from offsetx_apollo_builder.agent import CompanionError, CompanionStore, MemorySnapshot, RunRefused
from offsetx_apollo_builder.ai.tiers import DataClass


def profile(**kwargs):
    return Companion(**{'id': 'scout', 'name': 'Scout', 'instructions': 'Observe public facts',
                        'tools': ('read',), 'memory_scopes': ('public_research',), **kwargs})


def make_run(tmp_path, companion, answers, *, memory=(), trace=None, data_class=DataClass.INTERNAL):
    broker = _Broker(answers)
    page = _Page()
    trace = trace or Trace.open(tmp_path / 'traces')
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(
        enabled_provider_ids=('trusted',)), page=page, trace=trace,
        companion=companion, memory=memory, decision_data_class=data_class)
    return run, broker, page, trace


def test_profile_crud_is_private_persistent_and_workspace_scoped(tmp_path):
    store = CompanionStore(tmp_path)
    stored = profile()
    store.save(stored)
    assert CompanionStore(tmp_path).get('local', 'scout') == stored
    assert store.list('local') == [stored]
    path = tmp_path / 'companions/local/scout.json'
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    store.save(profile(workspace_id='other', name='Other Scout'))
    assert store.get('local', 'scout').name == 'Scout'
    assert store.get('other', 'scout').name == 'Other Scout'
    store.save(replace(stored, instructions='Updated instructions'))
    assert store.get('local', 'scout').instructions == 'Updated instructions'
    store.delete('local', 'scout')
    store.delete('local', 'scout')
    assert store.list('local') == []
    assert store.list('other')


def test_concurrent_profile_writes_do_not_lose_unrelated_profiles(tmp_path):
    def save(index):
        CompanionStore(tmp_path).save(profile(id=f'scout{index}'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(16)))
    assert len(CompanionStore(tmp_path).list('local')) == 16


@pytest.mark.parametrize('kwargs', [
    {'id': '../escape'}, {'workspace_id': '../other'}, {'name': ''},
    {'instructions': 'a' * 1501}, {'tools': ('evaluate',)}, {'tools': 'read'},
    {'tools': ('read', 'read')}, {'tools': (False,)},
    {'memory_scopes': ('../private',)}, {'memory_scopes': 'all'},
])
def test_invalid_profiles_are_rejected(kwargs):
    with pytest.raises(CompanionError):
        profile(**kwargs)


def test_corrupt_or_swapped_profile_fails_closed(tmp_path):
    store = CompanionStore(tmp_path)
    store.save(profile())
    path = tmp_path / 'companions/local/scout.json'
    for text in ('{', '[]', json.dumps(profile(workspace_id='other').to_dict()),
                 json.dumps({**profile().to_dict(), 'execute': 'shell'})):
        path.write_text(text)
        with pytest.raises(CompanionError):
            store.get('local', 'scout')


def test_paths_and_links_cannot_read_other_material(tmp_path):
    store = CompanionStore(tmp_path)
    for workspace, name in [('../outside', 'scout'), ('local', '../../outside')]:
        with pytest.raises(CompanionError):
            store.get(workspace, name)
    store.save(profile())
    outside = tmp_path / 'outside.json'; outside.write_text('{}')
    path = tmp_path / 'companions/local/scout.json'
    path.unlink(); path.symlink_to(outside)
    with pytest.raises(CompanionError):
        store.get('local', 'scout')
    with pytest.raises(CompanionError):
        store.save(profile())
    assert outside.read_text() == '{}'


def test_profile_controls_instructions_tools_and_scoped_memory_in_payload(tmp_path):
    memory = (MemorySnapshot('local', 'public_research', 'PERMITTED PUBLIC FINDING'),
              MemorySnapshot('local', 'private_notes', 'MUST NEVER LEAVE'))
    store = CompanionStore(tmp_path); store.save(profile())
    run, broker, page, trace = make_run(tmp_path, store.get('local', 'scout'), [
        '{"state":"act","action":"read","args":{}}', '{"state":"done","result":"Finished"}'], memory=memory)
    outcome = asyncio.run(run.run('Inspect public leads', step_budget=2))
    assert outcome.status == 'completed'
    assert page.actions == [('read', 20000)]
    for call in broker.calls:
        sent = call['request'].instructions
        assert 'Observe public facts' in sent
        assert 'GRANTED BROWSER VERBS: read' in sent
        assert 'PERMITTED PUBLIC FINDING' in sent
        assert 'MUST NEVER LEAVE' not in sent
        assert call['request'].data_class is DataClass.INTERNAL
    metadata = json.loads(trace.captured_text(next(s for s in trace.read() if s.kind == 'run_started')))
    assert metadata['companion'] == profile().to_dict()
    # Memory is pushed per run, never copied into the binding/audit metadata.
    assert 'PERMITTED PUBLIC FINDING' not in json.dumps(metadata)


@pytest.mark.parametrize('companion,memory,data_class', [
    (profile(workspace_id='other'), (), DataClass.INTERNAL),
    (profile(), (MemorySnapshot('other', 'public_research', 'SECRET'),), DataClass.INTERNAL),
    (None, (MemorySnapshot('local', 'public_research', 'SECRET'),), DataClass.INTERNAL),
    (profile(), (), DataClass.PUBLIC),
])
def test_workspace_or_class_escalation_is_refused_before_provider_call(tmp_path, companion, memory, data_class):
    run, broker, page, _ = make_run(tmp_path, companion, ['{"state":"done"}'], memory=memory, data_class=data_class)
    with pytest.raises(RunRefused):
        asyncio.run(run.run('Inspect leads', step_budget=2))
    assert broker.calls == []
    assert page.actions == []


def test_empty_grants_allow_completion_but_no_browser_verb(tmp_path):
    for answer, expected in [('{"state":"done"}', 'completed'),
        ('{"state":"act","action":"read","args":{}}', 'refused')]:
        run, _, page, _ = make_run(tmp_path, profile(tools=()), [answer])
        assert asyncio.run(run.run('Inspect leads', step_budget=1)).status == expected
        assert page.actions == []


def test_resume_cannot_drop_or_widen_original_grants(tmp_path):
    run, _, page, trace = make_run(tmp_path, profile(), ['{"state":"act","action":"read","args":{}}'])
    original = page.snapshot
    count = 0
    async def interrupted():
        nonlocal count
        count += 1
        if count > 1:
            raise RuntimeError('process interrupted')
        return await original()
    page.snapshot = interrupted
    with pytest.raises(RuntimeError, match='interrupted'):
        asyncio.run(run.run('Inspect leads', step_budget=3))
    for changed in (None, profile(tools=('read', 'click')), profile(workspace_id='other')):
        resumed, broker, _, _ = make_run(tmp_path, changed, ['{"state":"done"}'], trace=trace)
        with pytest.raises(RunRefused):
            asyncio.run(resumed.resume())
        assert broker.calls == []
    same, broker, _, _ = make_run(tmp_path, profile(), ['{"state":"done"}'], trace=trace)
    assert asyncio.run(same.resume()).status == 'completed'
    assert 'GRANTED BROWSER VERBS: read' in broker.calls[0]['request'].instructions


def test_oversized_combined_owner_context_refuses_instead_of_truncating_scope(tmp_path):
    run, broker, _, trace = make_run(tmp_path, profile(instructions='a' * 1500), ['{"state":"done"}'])
    (trace.directory / 'PLAN.md').write_text('b' * 4500)
    with pytest.raises(RunRefused, match='5000'):
        asyncio.run(run.run('Inspect leads', step_budget=2))
    assert broker.calls == []


@pytest.mark.parametrize('location', ['instructions', 'memory'])
def test_companion_secrets_use_real_egress_scanner(tmp_path, monkeypatch, location):
    from pathlib import Path
    from offsetx_apollo_builder.ai import EgressBroker, EgressBlocked, ProviderRegistry, QuotaTracker
    registry = ProviderRegistry(Path(__file__).parents[1] / 'config/providers.yaml')
    broker = EgressBroker(registry=registry, credential_resolver=lambda _: 'test-key',
                          quota=QuotaTracker(tmp_path), logger=lambda **kwargs: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('provider creation must not occur')
    monkeypatch.setattr(broker, '_instantiate', forbidden)
    secret = 'sk-abcdefghijklmnop1234567890'
    companion = profile(instructions=secret if location == 'instructions' else 'Read facts')
    memory = (MemorySnapshot('local', 'public_research', secret),) if location == 'memory' else ()
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(enabled_provider_ids=('mistral',)),
                   page=_Page(), trace=Trace.open(tmp_path / 'traces'), companion=companion, memory=memory)
    with pytest.raises(EgressBlocked):
        asyncio.run(run.run('Inspect leads', step_budget=1))


@pytest.mark.parametrize('action,args', [
    ('goto', {'url':'https://public.example.test'}), ('click', {'handle':1}),
    ('type', {'handle':1, 'text':'hello'}), ('press', {'key':'Enter'}),
    ('scroll', {'down':1}), ('select', {'handle':1, 'option':'choice'}),
    ('wait_for', {'text':'visible'}), ('read', {}), ('screenshot', {}), ('back', {})])
def test_every_verb_requires_a_host_grant(tmp_path, action, args):
    run, _, page, _ = make_run(tmp_path, profile(tools=()), [json.dumps(
        {'state':'act', 'action':action, 'args':args})])
    result = asyncio.run(run.run('Inspect leads', step_budget=1))
    assert result.status == 'refused'
    assert 'grant' in result.message.lower()
    assert page.actions == []
