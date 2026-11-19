"""A bounded worker over the durable frontier and existing guarded HTTP engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import requests

from ..browser.registry import RegistryError
from ..discovery import DiscoveryFetchError, ParsedPage, SafePublicFetcher, SKIPPED_FILE_SUFFIXES, parse_robots
from .frontier import Claim, CrawlDeferred, Frontier, FrontierError


class FrontierFetcher(SafePublicFetcher):
    """Persist public robots rules and defer paced requests instead of sleeping."""

    def __init__(self, frontier: Frontier, **kwargs) -> None:
        self.frontier = frontier
        self.claim: Claim | None = None
        self.document_url = self.robots_origin = ''
        super().__init__(frontier.policy, before_request=self._gate, on_redirect=self._redirect, **kwargs)

    def _gate(self, url: str, delay: float) -> None:
        if self.claim is None:
            raise FrontierError('Select a crawl claim before fetching a page.')
        try:
            self.frontier.before_request(self.claim, url, delay)
        except CrawlDeferred as exc:
            # A paused robots request still belongs to the current document.
            exc.url = self.document_url
            raise

    def _redirect(self, source: str, destination: str, is_document: bool) -> None:
        if self.claim is None:
            raise FrontierError('A redirect needs an active crawl claim.')
        destination = self.frontier.validate(destination)
        if is_document:
            self.frontier.redirect(self.claim, destination)
            return
        with self.frontier.db.transaction():
            self.frontier._owned(self.claim)
            row = self.frontier.db.execute('SELECT redirects FROM crawl_robots WHERE origin=? AND agent=?',
                (self.robots_origin, self.policy.user_agent)).fetchone()
            if row is None or row['redirects'] >= 3:
                raise FrontierError('Too many robots redirects; the crawl attempt stopped safely.')
            self.frontier.db.execute('UPDATE crawl_robots SET request_url=?,redirects=redirects+1 WHERE origin=? AND agent=?',
                (destination, self.robots_origin, self.policy.user_agent))

    def _robots_allowed(self, url: str) -> tuple[bool, float]:
        self.document_url = url
        parsed = urlsplit(url)
        origin = urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))
        self.robots_origin = origin
        now, agent = self.frontier.now(), self.policy.user_agent
        saved = self.frontier.db.execute('SELECT * FROM crawl_robots WHERE origin=? AND agent=?',
                                         (origin, agent)).fetchone()
        if saved is not None and not saved['request_url'] and 0 <= now-saved['checked_at'] < 3600:
            body = saved['body']
        else:
            pending = saved is not None and saved['request_url'] and 0 <= now-saved['request_started'] < 3600
            request_url = saved['request_url'] if pending else origin+'/robots.txt'
            if not pending:
                with self.frontier.db.transaction():
                    if self.claim is None:
                        raise FrontierError('A robots lookup needs an active crawl claim.')
                    self.frontier._owned(self.claim)
                    self.frontier.db.execute('DELETE FROM crawl_robots WHERE checked_at<? AND request_started<?', (now-86400, now-86400))
                    self.frontier.db.execute("INSERT INTO crawl_robots(origin,agent,body,checked_at,request_url,request_started) VALUES(?,?,'',-1,?,?) ON CONFLICT(origin,agent) DO UPDATE SET body='',checked_at=-1,request_url=excluded.request_url,request_started=excluded.request_started,redirects=0",
                                             (origin, agent, request_url, now))
            content, _, status = self._request_bytes(request_url, max_bytes=256000,
                accepted_types=('text/plain', 'text/*', 'text/html', ''))
            body = content.decode('utf-8', errors='replace') if status == 200 else ''
            with self.frontier.db.transaction():
                if self.claim is None:
                    raise FrontierError('A robots lookup needs an active crawl claim.')
                self.frontier._owned(self.claim)
                self.frontier.db.execute("UPDATE crawl_robots SET body=?,checked_at=?,request_url='',redirects=0 WHERE origin=? AND agent=?",
                                         (body, now, origin, agent))
        rules, delay = parse_robots(body.encode('utf-8'), origin+'/robots.txt', agent)
        return rules.can_fetch(agent, url), delay


@dataclass
class CrawlBatch:
    attempted: int = 0
    deferred: int = 0
    failed: int = 0
    new_urls: int = 0
    links_skipped: int = 0
    pages: list[ParsedPage] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    next_due: float | None = None

    def to_dict(self) -> dict:
        return {'attempted': self.attempted, 'fetched': len(self.pages), 'deferred': self.deferred,
                'failed': self.failed, 'new_urls': self.new_urls, 'links_skipped': self.links_skipped,
                'pages': [{'url': p.url, 'title': p.title, 'content_sha256': p.content_sha256} for p in self.pages],
                'errors': self.errors, 'next_due': self.next_due}


class FrontierRunner:
    def __init__(self, frontier: Frontier, *, fetcher=None) -> None:
        self.frontier = frontier
        self.fetcher = fetcher if fetcher is not None else FrontierFetcher(frontier)

    def run_due(self, *, max_pages: int = 20) -> CrawlBatch:
        if type(max_pages) is not int or not 1 <= max_pages <= 100:
            raise FrontierError('Each batch must attempt between 1 and 100 pages.')
        result = CrawlBatch()
        for _ in range(max_pages):
            claim = self.frontier.claim()
            if claim is None:
                break
            result.attempted += 1
            if isinstance(self.fetcher, FrontierFetcher):
                self.fetcher.claim = claim
            try:
                page = self.fetcher.fetch(claim.request_url or claim.url)
                self.frontier.finish(claim, page)
            except CrawlDeferred as exc:
                self.frontier.retry(claim, str(exc), until=exc.until, request_url=exc.url)
                result.deferred += 1
                continue
            except RegistryError:
                raise
            except (DiscoveryFetchError, ValueError, requests.RequestException) as exc:
                try:
                    self.frontier.retry(claim, str(exc))
                except FrontierError as recovery:
                    # An expired worker must never overwrite a replacement's result.
                    exc = FrontierError(f'{exc} Recovery refused: {recovery}')
                result.failed += 1
                result.errors.append({'url': claim.url, 'error': str(exc)[:500]})
                continue
            result.pages.append(page)
            if claim.depth >= self.frontier.policy.max_depth:
                continue
            for link in page.links[:1000]:
                try:
                    if any(urlsplit(link).path.lower().endswith(suffix) for suffix in SKIPPED_FILE_SUFFIXES):
                        result.links_skipped += 1
                        continue
                    result.new_urls += self.frontier.enqueue(link, depth=claim.depth+1)
                except FrontierError:
                    result.links_skipped += 1
            result.links_skipped += max(0, len(page.links)-1000)
        result.next_due = self.frontier.inspect(limit=1)['next_due']
        return result

    def close(self) -> None:
        close = getattr(self.fetcher, 'close', None)
        if close:
            close()
