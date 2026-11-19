"""S-03.02.05: declarations drive all existing browser boundaries."""
import asyncio
from copy import deepcopy

import pytest
import yaml

from offsetx_apollo_builder.browser import identity, policy, signin
from offsetx_apollo_builder.browser.budget import Budget, BudgetLedger
from offsetx_apollo_builder.browser.perceive import Node, Snapshot


def declaration():
    return {'platforms': [{'id': 'forum', 'label': 'Forum',
        'login_url': 'https://forum.example.test/login',
        'home_url': 'https://forum.example.test/home',
        'signed_in': ['my discussions'], 'signed_out': ['sign in'],
        'domains': ['forum.example.test'], 'min_seconds_between_actions': 3.0,
        'unattended': False, 'refuse': ['bulk_export'], 'confirm': ['connect'],
        'actions_per_hour': 2, 'actions_per_day': 5}]}


def configure(tmp_path, monkeypatch, data):
    path = tmp_path / 'platforms.yaml'
    path.write_text(yaml.safe_dump(data))
    monkeypatch.setenv('OFFSETX_BROWSER_PLATFORMS', str(path))
    return path


def test_declared_platform_drives_signin_connections_policy_and_budget(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, declaration())
    target = identity.platform('forum')
    class Page:
        unattended = False
        async def goto(self, url):
            self.url = url
        async def snapshot(self):
            return Snapshot(url=self.url, title='Forum', nodes=[
                Node(handle=1, role='button', name='My discussions', backend_id=1)])
    reading = asyncio.run(signin.open_login(Page(), 'forum'))
    assert reading.connected
    store = identity.ConnectionStore(tmp_path)
    store.record('local', reading, target, account='work')
    rows = identity.catalogue(store, 'local', ledger=BudgetLedger(tmp_path))['platforms']
    assert next(r for r in rows if r['account'] == 'forum:work')['state'] == 'connected'
    assert Budget.for_platform('forum') == Budget(2, 5)
    rule = policy.rule_for('https://sub.forum.example.test/thread')
    assert rule.min_seconds_between_actions == 3
    with pytest.raises(policy.Refused, match='attended'):
        policy.check_navigation(target.home_url, unattended=True)
    assert policy.check_action('connect', target.home_url)[1]
    assert policy.rule_for('https://forum.example.test.attacker.test').suffix == '*'


@pytest.mark.parametrize('field', ['login_url', 'signed_in', 'signed_out', 'domains',
    'actions_per_hour', 'actions_per_day', 'min_seconds_between_actions', 'unattended'])
def test_missing_field_is_refused_by_platform_name(tmp_path, monkeypatch, field):
    data = declaration()
    del data['platforms'][0][field]
    configure(tmp_path, monkeypatch, data)
    with pytest.raises(ValueError, match='forum'):
        identity.catalogue(identity.ConnectionStore(tmp_path), 'local')


@pytest.mark.parametrize('field,value', [
    ('login_url', 'file:///etc/passwd'), ('home_url', 'https://u:p@forum.example.test'),
    ('home_url', 'https://127.0.0.1/home'), ('home_url', 'https://forum.example.test:bad'),
    ('signed_in', 'profile'), ('signed_out', []), ('domains', ['*']),
    ('domains', ['localhost']), ('min_seconds_between_actions', float('nan')),
    ('min_seconds_between_actions', -1), ('actions_per_hour', True),
    ('actions_per_day', 0), ('unattended', 'false'), ('id', '../forum'),
    ('surprise', 'ignored')])
def test_unsafe_or_ambiguous_declaration_fails_closed(tmp_path, monkeypatch, field, value):
    data = declaration()
    data['platforms'][0][field] = value
    configure(tmp_path, monkeypatch, data)
    with pytest.raises(ValueError):
        identity.catalogue(identity.ConnectionStore(tmp_path), 'local')


def test_duplicate_id_or_domain_is_rejected(tmp_path, monkeypatch):
    for field in ('id', 'domains'):
        data = declaration()
        other = deepcopy(data['platforms'][0])
        other['id'] = 'other'
        if field == 'id':
            other['id'] = 'forum'
            other['domains'] = ['other.example.test']
        data['platforms'].append(other)
        configure(tmp_path, monkeypatch, data)
        with pytest.raises(ValueError):
            identity.catalogue(identity.ConnectionStore(tmp_path), 'local')


def test_duplicate_yaml_keys_are_not_silently_last_write_wins(tmp_path, monkeypatch):
    path = configure(tmp_path, monkeypatch, declaration())
    path.write_text(path.read_text() + '\nplatforms: []\n')
    with pytest.raises(ValueError, match='duplicate'):
        identity.catalogue(identity.ConnectionStore(tmp_path), 'local')


def test_registry_removal_preserves_connection_records_and_rollback(tmp_path, monkeypatch):
    path = configure(tmp_path, monkeypatch, declaration())
    original = path.read_text()
    store = identity.ConnectionStore(tmp_path)
    target = identity.platform('forum')
    store.record('local', identity.Reading('connected'), target, account='work')
    changed = declaration(); changed['platforms'][0]['id'] = 'newforum'
    path.write_text(yaml.safe_dump(changed))
    assert store.get('local', 'forum', 'work').state == 'connected'
    assert any(r['account'] == 'forum:work' for r in identity.catalogue(store, 'local')['platforms'])
    path.write_text(original)
    assert identity.platform('forum').label == 'Forum'
    assert store.get('local', 'forum', 'work').state == 'connected'


def test_valid_dns_names_with_consecutive_hyphens_are_supported(tmp_path, monkeypatch):
    data = declaration()
    row = data['platforms'][0]
    row['domains'] = ['my--forum.example.test']
    row['home_url'] = 'https://my--forum.example.test/home'
    row['login_url'] = 'https://my--forum.example.test/login'
    configure(tmp_path, monkeypatch, data)
    assert identity.platform('forum').home_url == row['home_url']
