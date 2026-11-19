"""S-05.01.01 acceptance: durable scheduling, isolation and claim integrity."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from offsetx_apollo_builder.discovery import CrawlPolicy, ParsedPage


def policy(**kwargs):
    return CrawlPolicy(**{'allowed_domains': ('example.test',), 'request_delay_seconds': 0, **kwargs})


def page(url, digest='a', links=()):
    return ParsedPage(url=url, title='Public research', text='Public text', links=list(links),
                      people=[], content_sha256=digest * 64)


def store(tmp_path, *, clock=None, **kwargs):
    from offsetx_apollo_builder.crawl import Frontier
    return Frontier(tmp_path / 'frontier.db', policy(), clock=clock or (lambda: 1000.0),
                    **{'revisit_seconds':10, 'max_revisit_seconds':80, **kwargs})


def test_frontier_persists_deduplicates_and_reports_an_actionable_empty_state(tmp_path):
    queue = store(tmp_path)
    assert queue.inspect()['next_due'] is None
    assert queue.enqueue('https://EXAMPLE.test/team#people')
    assert not queue.enqueue('https://example.test/team')
    queue.close()
    reopened = store(tmp_path)
    assert [r['url'] for r in reopened.inspect()['urls']] == ['https://example.test/team']
    assert reopened.inspect()['next_due'] == 1000
    reopened.close()


@pytest.mark.parametrize('url', ['https://linkedin.com/in/a', 'https://sub.instagram.com/a',
    'https://tiktok.com/', 'https://x.com/', 'http://127.0.0.1/', 'http://169.254.169.254/',
    'https://user:password@example.test/', 'file:///etc/passwd', 'https://other.test/',
    'https://example.test.attacker.test/', 'https://example.test:invalid/'])
def test_invalid_targets_never_enter_frontier(tmp_path, url):
    from offsetx_apollo_builder.crawl import FrontierError
    queue = store(tmp_path)
    with pytest.raises(FrontierError):
        queue.enqueue(url)
    assert queue.inspect()['urls'] == []
    queue.close()


def test_changed_pages_are_revisited_sooner_than_repeatedly_unchanged_pages(tmp_path):
    now = [1000.0]
    queue = store(tmp_path, clock=lambda: now[0])
    for suffix in ('changing', 'quiet'):
        queue.enqueue(f'https://example.test/{suffix}')
    for index in range(4):
        for _ in range(2):
            claim = queue.claim()
            assert claim
            digest = chr(ord('a') + index) if claim.url.endswith('changing') else 'f'
            queue.finish(claim, page(claim.url, digest))
        now[0] += 100
    urls = {r['url'].rsplit('/', 1)[-1]: r for r in queue.inspect()['urls']}
    assert urls['quiet']['interval_seconds'] == 80
    assert urls['changing']['interval_seconds'] == 10
    assert urls['quiet']['next_due'] > urls['changing']['next_due']
    queue.close()


def test_expired_claim_is_recovered_and_stale_writer_cannot_finish(tmp_path):
    from offsetx_apollo_builder.crawl import FrontierError
    now = [1000.0]
    queue = store(tmp_path, clock=lambda: now[0], lease_seconds=10)
    queue.enqueue('https://example.test/a')
    old = queue.claim(); assert old
    assert queue.claim() is None
    now[0] += 11
    current = queue.claim(); assert current and current.token != old.token
    with pytest.raises(FrontierError, match='claim'):
        queue.finish(old, page(old.url))
    queue.finish(current, page(current.url))
    queue.close()


def test_separate_workers_cannot_claim_the_same_url_or_host(tmp_path):
    queue = store(tmp_path)
    queue.enqueue('https://example.test/a'); queue.enqueue('https://example.test/b')
    def take(_):
        other = store(tmp_path)
        try:
            return other.claim()
        finally:
            other.close()
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = [c for c in pool.map(take, range(6)) if c]
    assert len(claims) == 1
    queue.close()


def test_workspace_queues_are_isolated_but_host_pacing_is_shared(tmp_path):
    left = store(tmp_path, workspace_id='one')
    right = store(tmp_path, workspace_id='two')
    left.enqueue('https://example.test/a'); right.enqueue('https://example.test/b')
    first = left.claim(); assert first
    assert right.claim() is None
    left.finish(first, page(first.url))
    assert right.claim()
    assert [r['url'] for r in left.inspect()['urls']] == ['https://example.test/a']
    assert [r['url'] for r in right.inspect()['urls']] == ['https://example.test/b']
    left.close(); right.close()


def test_enqueue_batch_is_atomic_and_bounded(tmp_path):
    from offsetx_apollo_builder.crawl import FrontierError
    queue = store(tmp_path, capacity=2)
    with pytest.raises(FrontierError):
        queue.seed(['https://example.test/a', 'https://linkedin.com/in/a'])
    assert queue.inspect()['urls'] == []
    queue.seed(['https://example.test/a', 'https://example.test/b'])
    with pytest.raises(FrontierError, match='capacity'):
        queue.enqueue('https://example.test/c')
    assert len(queue.inspect()['urls']) == 2
    queue.close()


def test_new_platform_policy_is_applied_to_existing_queue_before_inspection(tmp_path, monkeypatch):
    import yaml
    from test_browser_platform_registry import declaration
    from offsetx_apollo_builder.crawl import Frontier
    queue = Frontier(tmp_path / 'frontier.db', policy(allowed_domains=('forum.example.test',)))
    queue.enqueue('https://forum.example.test/home')
    config = tmp_path / 'platforms.yaml'; config.write_text(yaml.safe_dump(declaration()))
    monkeypatch.setenv('OFFSETX_BROWSER_PLATFORMS', str(config))
    assert queue.inspect()['urls'] == []
    assert queue.claim() is None
    queue.close()


def test_corrupt_registry_does_not_erase_queue(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser.registry import RegistryError
    queue = store(tmp_path); queue.enqueue('https://example.test/a')
    config = tmp_path / 'bad.yaml'; config.write_text('platforms: nope')
    monkeypatch.setenv('OFFSETX_BROWSER_PLATFORMS', str(config))
    with pytest.raises(RegistryError):
        queue.inspect()
    monkeypatch.delenv('OFFSETX_BROWSER_PLATFORMS')
    assert len(queue.inspect()['urls']) == 1
    queue.close()


def test_frontier_refuses_nonregular_database_without_blocking(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    fifo = tmp_path/'database.pipe'; os.mkfifo(fifo)
    script = '''
import sys
from offsetx_apollo_builder.crawl import Frontier, FrontierError
from offsetx_apollo_builder.discovery import CrawlPolicy
try:
    Frontier(sys.argv[1], CrawlPolicy(allowed_domains=('example.test',)))
except FrontierError:
    print('refused')
else:
    raise AssertionError('a pipe was opened as a database')
'''
    result = subprocess.run([sys.executable, '-c', script, str(fifo)], cwd=Path(__file__).parents[1],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.strip() == 'refused'


def test_private_database_permissions_and_symlink_refusal(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier, FrontierError
    queue = store(tmp_path)
    assert (tmp_path/'frontier.db').stat().st_mode & 0o777 == 0o600
    queue.close()
    linked = tmp_path/'linked.db'; linked.symlink_to(tmp_path/'frontier.db')
    with pytest.raises(FrontierError):
        Frontier(linked, policy())


def test_invalid_settings_and_nonfinite_clock_fail_before_queue_mutation(tmp_path):
    from offsetx_apollo_builder.crawl import FrontierError
    for values in ({'capacity':True}, {'lease_seconds':float('nan')}, {'revisit_seconds':0},
                   {'revisit_seconds':100, 'max_revisit_seconds':10}):
        with pytest.raises(FrontierError):
            store(tmp_path, **values)
    queue = store(tmp_path, clock=lambda: float('nan'))
    with pytest.raises(FrontierError):
        queue.enqueue('https://example.test/a')
    queue.close()


def test_quoted_url_cannot_change_sql_and_invalid_hash_does_not_complete_claim(tmp_path):
    from offsetx_apollo_builder.crawl import FrontierError
    queue = store(tmp_path)
    url = "https://example.test/a?q=';DROP%20TABLE%20crawl_urls;--"
    queue.enqueue(url)
    claim = queue.claim()
    with pytest.raises(FrontierError, match='hash'):
        queue.finish(claim, page(url, 'not-a-hash'))
    assert queue.inspect()['total'] == 1
    queue.finish(claim, page(url))
    assert queue.inspect()['urls'][0]['checks'] == 1
    queue.close()


def test_lower_depth_limit_does_not_fetch_previously_queued_deeper_urls(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    queue = store(tmp_path)
    queue.enqueue('https://example.test/deep', depth=1); queue.close()
    shallow = Frontier(tmp_path/'frontier.db', policy(max_depth=0), clock=lambda: 1000.0)
    assert shallow.claim() is None
    assert shallow.inspect()['next_due'] is None
    shallow.close()


def test_remove_frees_capacity_but_refuses_an_active_claim(tmp_path):
    from offsetx_apollo_builder.crawl import FrontierError
    queue = store(tmp_path, capacity=1)
    queue.enqueue('https://example.test/a')
    claim = queue.claim()
    with pytest.raises(FrontierError, match='claimed'):
        queue.remove(claim.url)
    queue.finish(claim, page(claim.url))
    assert queue.remove('https://example.test/a#fragment')
    assert not queue.remove('https://example.test/a')
    assert queue.enqueue('https://example.test/b')
    queue.close()


def test_actual_processes_share_the_same_host_claim(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    queue = store(tmp_path)
    queue.seed(['https://example.test/a', 'https://example.test/b'])
    script = '''
import json,sys
from offsetx_apollo_builder.crawl import Frontier
from offsetx_apollo_builder.discovery import CrawlPolicy
queue=Frontier(sys.argv[1],CrawlPolicy(allowed_domains=('example.test',)),clock=lambda:1000.0)
try:
    print(json.dumps({'claimed': queue.claim() is not None}))
finally:
    queue.close()
'''
    def take(_):
        result = subprocess.run([sys.executable, '-c', script, str(tmp_path/'frontier.db')],
            cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)['claimed']
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(take, range(4))) == 1
    queue.close()
