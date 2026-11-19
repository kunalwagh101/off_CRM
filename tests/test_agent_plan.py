"""S-02.02.02: the owner plan is live, private and cannot redirect file reads."""
import asyncio
from html.parser import HTMLParser

import pytest

from offsetx_apollo_builder.agent import AgentRun, RunRefused
from offsetx_apollo_builder.agent.report import render
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.browser.trace import Trace
from test_agent_run import _Broker, _Page

DONE = '{"state":"done","result":"Finished"}'
CLICK = '{"state":"act","action":"click","args":{"handle":1}}'


def agent(tmp_path, answers, page=None):
    broker = _Broker(answers)
    trace = Trace.open(tmp_path)
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(
        enabled_provider_ids=('trusted',)), page=page or _Page(), trace=trace)
    return run, broker, trace


def test_started_run_has_one_private_plan_and_a_report_checklist(tmp_path):
    run, broker, trace = agent(tmp_path, [DONE])
    asyncio.run(run.run('Review leads', step_budget=2))
    plans = list(trace.directory.glob('PLAN.md'))
    assert len(plans) == 1
    assert 'Review leads' in plans[0].read_text()
    assert plans[0].stat().st_mode & 0o777 == 0o600
    assert 'OWNER PLAN' in broker.calls[0]['request'].instructions
    assert 'type="checkbox"' in render(trace)


def test_owner_edit_is_seen_on_the_very_next_decision(tmp_path):
    run, broker, trace = agent(tmp_path, [CLICK, DONE])
    original = run.page.click
    async def edit_after_click(*args, **kwargs):
        result = await original(*args, **kwargs)
        (trace.directory / 'PLAN.md').write_text('# Changed goal\n- [x] First step\n- [ ] Find only public companies')
        return result
    run.page.click = edit_after_click
    asyncio.run(run.run('Review leads', step_budget=3))
    assert 'Find only public companies' not in broker.calls[0]['request'].instructions
    assert 'Find only public companies' in broker.calls[1]['request'].instructions
    assert 'checked' in render(trace)


def test_restart_keeps_the_owner_plan(tmp_path):
    run, _, trace = agent(tmp_path, [DONE])
    plan = trace.directory / 'PLAN.md'
    plan.write_text('# Owner plan\n- [ ] Keep this exact text')
    asyncio.run(run.run('Review leads', step_budget=2))
    assert plan.read_text() == '# Owner plan\n- [ ] Keep this exact text'


@pytest.mark.parametrize('kind', ['symlink', 'directory', 'oversize', 'empty', 'invalid_utf8'])
def test_unreadable_or_unsafe_plan_refuses_before_egress(tmp_path, kind):
    run, broker, trace = agent(tmp_path, [DONE])
    plan = trace.directory / 'PLAN.md'
    if kind == 'symlink':
        other = tmp_path / 'outside'; other.write_text('private material')
        plan.symlink_to(other)
    elif kind == 'directory':
        plan.mkdir()
    elif kind == 'oversize':
        plan.write_text('a' * 20000)
    elif kind == 'invalid_utf8':
        plan.write_bytes(b'\xff')
    else:
        plan.write_text(' ')
    with pytest.raises(RunRefused, match='plan|PLAN'):
        asyncio.run(run.run('Review leads', step_budget=2))
    assert broker.calls == []


def test_deleted_midrun_plan_stops_instead_of_recreating_it(tmp_path):
    run, broker, trace = agent(tmp_path, [CLICK, DONE])
    original = run.page.click
    async def delete(*args, **kwargs):
        result = await original(*args, **kwargs)
        (trace.directory / 'PLAN.md').unlink()
        return result
    run.page.click = delete
    with pytest.raises(RunRefused, match='plan|PLAN'):
        asyncio.run(run.run('Review leads', step_budget=3))
    assert len(broker.calls) == 1


def test_plan_html_is_rendered_as_text_not_executable_markup(tmp_path):
    run, _, trace = agent(tmp_path, [DONE])
    (trace.directory / 'PLAN.md').write_text('- [ ] <script>alert(1)</script><img src=x onerror=alert(2)>')
    asyncio.run(run.run('Review leads', step_budget=2))
    class Tags(HTMLParser):
        tags = []
        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
    parser = Tags(); parser.feed(render(trace))
    assert 'script' not in parser.tags
    assert 'img' not in parser.tags


def test_resume_reopens_same_plan_and_reads_owner_changes(tmp_path):
    from test_agent_resume import _interrupted_run
    trace, page = _interrupted_run(tmp_path, root=tmp_path / 'traces')
    plan = trace.directory / 'PLAN.md'
    plan.write_text('# Continue here\n- [ ] Inspect the public summary')
    reopened = Trace.open(tmp_path / 'traces', run_id=trace.run_id)
    broker = _Broker([DONE])
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(
        enabled_provider_ids=('trusted',)), page=page, trace=reopened)
    # Replace the harness snapshot that simulated process death.
    from test_agent_resume import _Page as ResumePage
    run.page = ResumePage()
    asyncio.run(run.resume())
    assert 'Inspect the public summary' in broker.calls[0]['request'].instructions
    assert len(list((tmp_path / 'traces').rglob('PLAN.md'))) == 1


def test_plan_secret_is_blocked_by_real_broker_before_provider_creation(tmp_path, monkeypatch):
    from pathlib import Path
    from offsetx_apollo_builder.ai import EgressBroker, EgressBlocked, ProviderRegistry, QuotaTracker
    registry = ProviderRegistry(Path(__file__).parents[1] / 'config/providers.yaml')
    broker = EgressBroker(registry=registry, credential_resolver=lambda _: 'test-key',
                          quota=QuotaTracker(tmp_path), logger=lambda **kwargs: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('provider must not be created')
    monkeypatch.setattr(broker, '_instantiate', forbidden)
    trace = Trace.open(tmp_path / 'traces')
    (trace.directory / 'PLAN.md').write_text('- [ ] Use key sk-abcdefghijklmnop1234567890')
    run = AgentRun(broker=broker, settings=WorkspaceEgressSettings(
        enabled_provider_ids=('mistral',)), page=_Page(), trace=trace)
    with pytest.raises(EgressBlocked):
        asyncio.run(run.run('Review leads', step_budget=2))
