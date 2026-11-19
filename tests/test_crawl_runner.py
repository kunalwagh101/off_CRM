"""Real guarded fetch/parser integration with an in-process HTTP transport fixture."""
from dataclasses import replace

import pytest

from offsetx_apollo_builder.crawl import FrontierFetcher, FrontierRunner
from offsetx_apollo_builder.discovery import DiscoveryFetchError
from test_crawl_fetch_safety import Response, Session, public_dns
from test_crawl_frontier import page, store


def test_long_robots_delay_defers_without_sleep_and_survives_worker_restart(tmp_path):
    now = [1000.0]
    queue = store(tmp_path, clock=lambda: now[0])
    queue.enqueue('https://example.test/a')
    first = Session({'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /\nCrawl-delay: 120'),
                     'https://example.test/a': Response(b'<html><body>public</body></html>', **{'Content-Type':'text/html'})})
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=first, resolver=public_dns))
    batch = worker.run_due(max_pages=1)
    assert batch.deferred == 1 and batch.failed == 0 and batch.pages == []
    assert batch.next_due == 1120
    assert first.urls == ['https://example.test/robots.txt']
    worker.close(); queue.close()
    now[0] = 1120
    queue = store(tmp_path, clock=lambda: now[0])
    second = Session({'https://example.test/a': Response(b'<html><body>public</body></html>', **{'Content-Type':'text/html'})})
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=second, resolver=public_dns))
    result = worker.run_due(max_pages=1)
    assert len(result.pages) == 1
    assert second.urls == ['https://example.test/a']
    assert queue.inspect()['urls'][0]['checks'] == 1
    worker.close(); queue.close()


def test_runner_expands_only_safe_links_within_depth_and_attempt_budget(tmp_path):
    queue = store(tmp_path)
    queue.seed(['https://example.test/a', 'https://example.test/b'])
    class Fetcher:
        def fetch(self, url):
            return page(url, links=['https://example.test/c', 'https://linkedin.com/in/a',
                                   'http://127.0.0.1/private', 'https://example.test/document.pdf'])
    runner = FrontierRunner(queue, fetcher=Fetcher())
    result = runner.run_due(max_pages=1)
    assert result.attempted == 1 and len(result.pages) == 1
    assert result.new_urls == 1 and result.links_skipped == 3
    assert len(queue.inspect()['urls']) == 3
    assert runner.run_due(max_pages=5).new_urls == 0
    queue.close()


def test_failures_back_off_without_discarding_other_work(tmp_path):
    queue = store(tmp_path)
    queue.seed(['https://example.test/bad', 'https://example.test/good'])
    class Fetcher:
        def fetch(self, url):
            if url.endswith('bad'):
                raise DiscoveryFetchError('robots.txt disallows this page')
            return page(url)
    batch = FrontierRunner(queue, fetcher=Fetcher()).run_due(max_pages=2)
    assert batch.failed == 1 and len(batch.pages) == 1
    bad = next(r for r in queue.inspect()['urls'] if r['url'].endswith('bad'))
    assert bad['next_due'] == 1060 and bad['failures'] == 1
    queue.close()


def test_private_dns_answer_is_refused_before_transport(tmp_path):
    queue = store(tmp_path); queue.enqueue('https://example.test/a')
    session = Session({})
    resolver = lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))]
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=resolver))
    result = worker.run_due(max_pages=1)
    assert result.failed == 1 and session.urls == []
    worker.close(); queue.close()


def test_redirect_to_session_gated_platform_is_refused_before_transport(tmp_path):
    queue = store(tmp_path); queue.enqueue('https://example.test/a')
    session = Session({
        'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /'),
        'https://example.test/a': Response(status=302, Location='https://linkedin.com/in/a'),
    })
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=public_dns))
    assert worker.run_due(max_pages=1).failed == 1
    assert all('linkedin' not in url for url in session.urls)
    worker.close(); queue.close()


def test_backup_restores_queue_and_observed_content_without_legacy_migration(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    from test_crawl_frontier import policy
    import sqlite3
    source = store(tmp_path); source.enqueue('https://example.test/a')
    claim = source.claim(); source.finish(claim, page(claim.url))
    backup = tmp_path / 'backup.db'
    # SQLite's backup API gives a consistent snapshot even while WAL is enabled.
    target = sqlite3.connect(backup)
    source.db.raw.backup(target); target.close(); source.close()
    restored = Frontier(backup, policy(), clock=lambda: 1000.0)
    row = restored.inspect()['urls'][0]
    assert row['content_hash'] == 'a' * 64 and row['checks'] == 1
    restored.close()


def test_foreign_redirect_robots_refusal_survives_the_persistent_runner(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    from test_crawl_frontier import policy
    queue = Frontier(tmp_path/'frontier.db', policy(allowed_domains=('example.test',)), clock=lambda: 1000.0)
    queue.enqueue('https://example.test/start')
    session = Session({
        'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /'),
        'https://example.test/start': Response(status=302, Location='https://other.example.test/private'),
        'https://other.example.test/robots.txt': Response(b'User-agent: *\nDisallow: /private'),
    })
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=public_dns))
    assert worker.run_due(max_pages=1).failed == 1
    assert 'https://other.example.test/private' not in session.urls
    worker.close(); queue.close()


def test_paced_redirect_resumes_at_destination_instead_of_looping_at_source(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    from test_crawl_frontier import policy
    now = [1000.0]
    queue = Frontier(tmp_path/'paced.db', policy(request_delay_seconds=1), clock=lambda: now[0])
    queue.enqueue('https://example.test/start')
    session = Session({
        'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /'),
        'https://example.test/start': Response(status=302, Location='/finish'),
        'https://example.test/finish': Response(b'<html><body>finished</body></html>', **{'Content-Type':'text/html'}),
    })
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=public_dns))
    results = []
    for _ in range(4):
        result = worker.run_due(max_pages=1); results.extend(result.pages)
        if results:
            break
        now[0] = result.next_due
    assert [p.url for p in results] == ['https://example.test/finish']
    assert session.urls.count('https://example.test/start') == 1
    worker.close(); queue.close()


def test_paced_robots_redirect_also_resumes_after_worker_restart(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    from test_crawl_frontier import policy
    now = [1000.0]
    session = Session({
        'https://example.test/robots.txt': Response(status=302, Location='/public-robots'),
        'https://example.test/public-robots': Response(b'User-agent: *\nAllow: /'),
        'https://example.test/a': Response(b'<html><body>finished</body></html>', **{'Content-Type':'text/html'}),
    })
    pages = []
    for attempt in range(5):
        queue = Frontier(tmp_path/'paced-robots.db', policy(request_delay_seconds=1), clock=lambda: now[0])
        if attempt == 0:
            queue.enqueue('https://example.test/a')
        worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=public_dns))
        batch = worker.run_due(max_pages=1); pages.extend(batch.pages)
        worker.close(); queue.close()
        if pages:
            break
        now[0] = batch.next_due
    assert len(pages) == 1
    assert session.urls == ['https://example.test/robots.txt', 'https://example.test/public-robots', 'https://example.test/a']


def test_redirect_limit_cannot_reset_itself_by_deferring_each_hop(tmp_path):
    from offsetx_apollo_builder.crawl import Frontier
    from test_crawl_frontier import policy
    now = [1000.0]
    queue = Frontier(tmp_path/'redirect-limit.db', policy(request_delay_seconds=1), clock=lambda: now[0])
    queue.enqueue('https://example.test/hop0')
    responses = {'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /')}
    responses.update({f'https://example.test/hop{i}': Response(status=302, Location=f'/hop{i+1}') for i in range(6)})
    session = Session(responses)
    worker = FrontierRunner(queue, fetcher=FrontierFetcher(queue, session=session, resolver=public_dns))
    for _ in range(10):
        batch = worker.run_due(max_pages=1)
        if batch.failed:
            break
        now[0] = batch.next_due
    assert batch.failed == 1
    assert 'redirects' in batch.errors[0]['error']
    assert 'https://example.test/hop4' not in session.urls
    worker.close(); queue.close()
