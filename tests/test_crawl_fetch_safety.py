"""S-05.01.01: robots rules apply to every document destination."""
from urllib.robotparser import RobotFileParser

import pytest

from offsetx_apollo_builder.discovery import CrawlPolicy, DiscoveryFetchError, SafePublicFetcher


class Response:
    def __init__(self, body=b'', status=200, **headers):
        self.body, self.status_code = body, status
        self.headers = {'Content-Type': 'text/plain', **headers}
    def iter_content(self, **kwargs):
        yield self.body
    def close(self):
        pass


class Session:
    def __init__(self, responses):
        self.responses, self.urls = responses, []
        self.cookies = type('Cookies', (), {'clear': lambda _: None})()
    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.responses[url]
    def close(self):
        pass


def public_dns(*args, **kwargs):
    return [(2, 1, 6, '', ('93.184.216.34', 443))]


def fetcher(responses, **kwargs):
    session = Session(responses)
    item = SafePublicFetcher(CrawlPolicy(allowed_domains=('example.test',), request_delay_seconds=0),
                             session=session, resolver=public_dns, **kwargs)
    return item, session


def test_robots_crawl_delay_is_not_shortened_to_thirty_seconds():
    item, _ = fetcher({'https://example.test/robots.txt': Response(
        b'User-agent: *\nAllow: /\nCrawl-delay: 120\n')})
    assert item._robots_allowed('https://example.test/page') == (True, 120)


def test_redirect_destination_robots_are_checked_before_fetch():
    item, session = fetcher({
        'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /'),
        'https://example.test/start': Response(status=302, Location='https://other.example.test/secret'),
        'https://other.example.test/robots.txt': Response(b'User-agent: *\nDisallow: /secret'),
        'https://other.example.test/secret': Response(b'<html><body>private</body></html>', **{'Content-Type':'text/html'}),
    })
    with pytest.raises(DiscoveryFetchError, match='robots'):
        item.fetch('https://example.test/start')
    assert 'https://other.example.test/secret' not in session.urls


def test_robots_cache_does_not_cross_origins_or_ports():
    item, _ = fetcher({
        'https://example.test/robots.txt': Response(b'User-agent: *\nAllow: /'),
        'http://example.test/robots.txt': Response(b'User-agent: *\nDisallow: /'),
    })
    assert item._robots_allowed('https://example.test/page')[0]
    assert not item._robots_allowed('http://example.test/page')[0]


def test_fractional_robots_delays_are_not_ignored():
    item, _ = fetcher({'https://example.test/robots.txt': Response(
        b'User-agent: *\nAllow: /\nCrawl-delay: 0.5\n')})
    assert item._robots_allowed('https://example.test/a')[1] >= 0.5
