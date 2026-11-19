"""Durable public-URL scheduling and host leases for local crawler workers."""
from __future__ import annotations

import math
import os
import re
import stat
import time
import uuid
from itertools import islice
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit

from ..browser.policy import declared_rules
from ..db import SQLiteDatabase
from ..discovery import BLOCKED_SOCIAL_DOMAINS, CrawlPolicy, ParsedPage, canonical_url, validate_public_url

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_urls (
 workspace TEXT NOT NULL, url TEXT NOT NULL, host TEXT NOT NULL, depth INTEGER NOT NULL,
 next_due REAL NOT NULL, interval_seconds REAL NOT NULL, state TEXT NOT NULL DEFAULT 'ready',
 content_hash TEXT NOT NULL DEFAULT '', title TEXT NOT NULL DEFAULT '',
 last_checked REAL, last_changed REAL, checks INTEGER NOT NULL DEFAULT 0,
 failures INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
 token TEXT NOT NULL DEFAULT '', lease_until REAL NOT NULL DEFAULT 0,
 resume_url TEXT NOT NULL DEFAULT '', redirects INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(workspace, url)
);
CREATE INDEX IF NOT EXISTS crawl_due ON crawl_urls(workspace, next_due);
CREATE TABLE IF NOT EXISTS crawl_hosts (
 host TEXT PRIMARY KEY, next_at REAL NOT NULL DEFAULT 0, last_at REAL,
 token TEXT NOT NULL DEFAULT '', lease_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS crawl_robots (
 origin TEXT NOT NULL, agent TEXT NOT NULL, body TEXT NOT NULL, checked_at REAL NOT NULL,
 request_url TEXT NOT NULL DEFAULT '', redirects INTEGER NOT NULL DEFAULT 0, request_started REAL NOT NULL DEFAULT 0,
 PRIMARY KEY(origin, agent)
);
"""


class FrontierError(ValueError):
    """A queue operation could not safely complete."""


class CrawlDeferred(Exception):
    def __init__(self, until: float, url: str = '') -> None:
        super().__init__('Host pacing requires a later attempt.')
        self.until, self.url = until, url


@dataclass(frozen=True)
class Claim:
    url: str
    depth: int
    token: str
    request_url: str = ''


class Frontier:
    def __init__(self, path: Path | str, policy: CrawlPolicy, *, workspace_id: str = 'local',
                 clock: Callable[[], float] = time.time, revisit_seconds: float = 86400,
                 max_revisit_seconds: float = 2592000, lease_seconds: float = 600,
                 capacity: int = 10000) -> None:
        if not isinstance(workspace_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', workspace_id):
            raise FrontierError('Use a workspace identifier of 1–64 letters, numbers, dashes or underscores.')
        for value in (revisit_seconds, max_revisit_seconds, lease_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise FrontierError('Revisit intervals and claim leases must be finite positive seconds.')
        if max_revisit_seconds < revisit_seconds or not 1 <= lease_seconds <= 86400:
            raise FrontierError('Maximum revisit must cover the base interval; leases must be 1–86400 seconds.')
        if type(capacity) is not int or not 1 <= capacity <= 100000:
            raise FrontierError('Frontier capacity must be an integer between 1 and 100000 URLs.')
        if not policy.obey_robots:
            raise FrontierError('The persistent crawler always honours robots.txt.')
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError('not a regular database file')
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
        except OSError as exc:
            raise FrontierError('Cannot open the frontier file. Use a writable regular SQLite file.') from exc
        self.db = SQLiteDatabase(str(path))
        self.db.executescript(SCHEMA)
        self.policy, self.workspace_id, self.clock = policy, workspace_id, clock
        self.revisit_seconds, self.max_revisit_seconds = revisit_seconds, max_revisit_seconds
        self.lease_seconds, self.capacity = lease_seconds, capacity

    def now(self) -> float:
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise FrontierError('The scheduler clock must return a finite nonnegative UTC timestamp.')
        return float(now)

    def _blocked_domains(self) -> tuple[str, ...]:
        # A corrupt registry must fail before pruning can remove any targets.
        restricted = tuple(r.suffix for r in declared_rules() if not r.unattended)
        return tuple(set(BLOCKED_SOCIAL_DOMAINS + self.policy.blocked_domains + restricted))

    def validate(self, url: str) -> str:
        return self._validate(url, self._blocked_domains())

    def _validate(self, url: str, blocked: tuple[str, ...]) -> str:
        if not isinstance(url, str) or not url.strip() or len(url) > 8192:
            raise FrontierError('Crawler URLs must contain between 1 and 8192 characters.')
        try:
            return validate_public_url(url, allowed_domains=self.policy.allowed_domains,
                blocked_domains=blocked)
        except (ValueError, TypeError) as exc:
            raise FrontierError(f'Crawler target refused: {exc}') from exc

    def _prune(self) -> None:
        blocked = self._blocked_domains()
        rows = self.db.execute('SELECT url,resume_url FROM crawl_urls WHERE workspace=?', (self.workspace_id,)).fetchall()
        removed = []
        for row in rows:
            try:
                self._validate(row['url'], blocked)
                if row['resume_url']:
                    self._validate(row['resume_url'], blocked)
            except FrontierError:
                removed.append(row['url'])
        if removed:
            with self.db.transaction():
                for url in removed:
                    self.db.execute('DELETE FROM crawl_urls WHERE workspace=? AND url=?', (self.workspace_id, url))

    def seed(self, urls: Iterable[str], *, depth: int = 0) -> int:
        if type(depth) is not int or not 0 <= depth <= self.policy.max_depth:
            raise FrontierError('URL depth must fit the configured crawl depth.')
        raw = list(islice(urls, 1001))
        if not raw or len(raw) > 1000:
            raise FrontierError('Seed between 1 and 1000 public URLs at a time.')
        blocked = self._blocked_domains()
        validated = tuple(dict.fromkeys(self._validate(url, blocked) for url in raw))
        now = self.now()
        with self.db.transaction():
            current = {r['url'] for r in self.db.execute('SELECT url FROM crawl_urls WHERE workspace=?', (self.workspace_id,)).fetchall()}
            added = [url for url in validated if url not in current]
            if len(current) + len(added) > self.capacity:
                raise FrontierError('Frontier capacity reached. Remove unused targets or increase capacity explicitly.')
            for url in added:
                self.db.execute('INSERT INTO crawl_urls(workspace,url,host,depth,next_due,interval_seconds) VALUES(?,?,?,?,?,?)',
                    (self.workspace_id, url, self.host(url), depth, now, self.revisit_seconds))
            for url in validated:
                self.db.execute('UPDATE crawl_urls SET depth=MIN(depth,?) WHERE workspace=? AND url=?', (depth, self.workspace_id, url))
        return len(added)

    def enqueue(self, url: str, *, depth: int = 0) -> bool:
        return bool(self.seed([url], depth=depth))

    def remove(self, url: str) -> bool:
        if not isinstance(url, str) or len(url) > 8192:
            raise FrontierError('Specify the public URL to remove.')
        # Removing an old public target never requires expanding today's allow-list.
        url = canonical_url(validate_public_url(url, blocked_domains=()))
        with self.db.transaction():
            row = self.db.execute('SELECT lease_until FROM crawl_urls WHERE workspace=? AND url=?',
                                  (self.workspace_id, url)).fetchone()
            if row is None:
                return False
            if row['lease_until'] > self.now():
                raise FrontierError('This URL is claimed by a worker. Stop it or wait for its lease before removing the URL.')
            self.db.execute('DELETE FROM crawl_urls WHERE workspace=? AND url=?', (self.workspace_id, url))
        return True

    @staticmethod
    def host(url: str) -> str:
        return (urlsplit(url).hostname or '').lower().rstrip('.')

    def inspect(self, *, limit: int = 1000) -> dict:
        if type(limit) is not int or not 1 <= limit <= 10000:
            raise FrontierError('Inspection limit must be between 1 and 10000 URLs.')
        self._prune()
        rows = self.db.execute('SELECT * FROM crawl_urls WHERE workspace=? ORDER BY next_due,url LIMIT ?',
                               (self.workspace_id, limit)).fetchall()
        count = self.db.execute('''SELECT COUNT(*) AS n, MIN(CASE WHEN u.depth<=? THEN MAX(u.next_due,u.lease_until,COALESCE(h.next_at,0),COALESCE(h.lease_until,0)) END) AS due FROM crawl_urls u LEFT JOIN crawl_hosts h ON h.host=u.host WHERE u.workspace=?''',
                                (self.policy.max_depth, self.workspace_id)).fetchone()
        return {'workspace': self.workspace_id, 'total': count['n'], 'next_due': count['due'],
                'urls': [{**{k: r[k] for k in r.keys() if k != 'token'}, 'eligible': r['depth'] <= self.policy.max_depth} for r in rows],
                'action': ('Seed a permitted public URL.' if not count['n'] else
                           'Increase the crawl depth to process deeper queued URLs.' if count['due'] is None else
                           'Run due work, or wait until next_due.')}

    def claim(self) -> Claim | None:
        self._prune()
        now, token = self.now(), uuid.uuid4().hex
        with self.db.transaction():
            row = self.db.execute('''SELECT u.* FROM crawl_urls u LEFT JOIN crawl_hosts h ON h.host=u.host
                WHERE u.workspace=? AND u.depth<=? AND u.next_due<=? AND u.lease_until<=?
                AND COALESCE(h.next_at,0)<=? AND COALESCE(h.lease_until,0)<=?
                ORDER BY u.next_due,u.url LIMIT 1''', (self.workspace_id, self.policy.max_depth, now, now, now, now)).fetchone()
            if row is None:
                return None
            self.db.execute("UPDATE crawl_urls SET state='fetching',token=?,lease_until=? WHERE workspace=? AND url=?",
                            (token, now+self.lease_seconds, self.workspace_id, row['url']))
            self.db.execute('INSERT INTO crawl_hosts(host,token,lease_until) VALUES(?,?,?) ON CONFLICT(host) DO UPDATE SET token=excluded.token,lease_until=excluded.lease_until',
                            (row['host'], token, now+self.lease_seconds))
        return Claim(row['url'], row['depth'], token, row['resume_url'] or row['url'])

    def _owned(self, claim: Claim):
        row = self.db.execute('SELECT * FROM crawl_urls WHERE workspace=? AND url=? AND token=? AND lease_until>?',
                              (self.workspace_id, claim.url, claim.token, self.now())).fetchone()
        if row is None:
            raise FrontierError('The crawl claim expired or changed owner; its result was not committed.')
        return row

    def before_request(self, claim: Claim, url: str, delay: float) -> None:
        self.validate(url)
        if not math.isfinite(delay) or delay < 0:
            raise FrontierError('Host delay must be finite and nonnegative.')
        now, host = self.now(), self.host(url)
        with self.db.transaction():
            self._owned(claim)
            row = self.db.execute('SELECT * FROM crawl_hosts WHERE host=?', (host,)).fetchone()
            until = max(float(row['next_at']), row['last_at']+delay if row['last_at'] is not None else 0) if row else 0.0
            if row and row['token'] not in ('', claim.token) and row['lease_until'] > now:
                until = max(until, row['lease_until'])
            if until > now:
                raise CrawlDeferred(until, url)
            self.db.execute('INSERT INTO crawl_hosts(host,next_at,last_at,token,lease_until) VALUES(?,?,?,?,?) ON CONFLICT(host) DO UPDATE SET next_at=excluded.next_at,last_at=excluded.last_at,token=excluded.token,lease_until=excluded.lease_until',
                            (host, now+delay, now, claim.token, now+self.lease_seconds))
            self.db.execute('UPDATE crawl_urls SET lease_until=? WHERE workspace=? AND url=? AND token=?',
                            (now+self.lease_seconds, self.workspace_id, claim.url, claim.token))

    def _release(self, claim: Claim) -> None:
        self.db.execute("UPDATE crawl_hosts SET token='',lease_until=0 WHERE token=?", (claim.token,))

    def finish(self, claim: Claim, page: ParsedPage) -> None:
        self.validate(page.url)
        if not re.fullmatch('[0-9a-f]{64}', page.content_sha256):
            raise FrontierError('A fetched page needs a SHA-256 content hash.')
        now = self.now()
        with self.db.transaction():
            row = self._owned(claim)
            changed = page.content_sha256 != row['content_hash']
            interval = self.revisit_seconds if changed else min(self.max_revisit_seconds, row['interval_seconds']*2)
            self.db.execute('''UPDATE crawl_urls SET state='ready',content_hash=?,title=?,last_checked=?,
                last_changed=?,checks=checks+1,failures=0,last_error='',next_due=?,interval_seconds=?,token='',lease_until=0,resume_url='',redirects=0
                WHERE workspace=? AND url=? AND token=?''',
                (page.content_sha256, page.title[:500], now, now if changed else row['last_changed'],
                 now+interval, interval, self.workspace_id, claim.url, claim.token))
            self._release(claim)

    def redirect(self, claim: Claim, destination: str) -> None:
        destination = self.validate(destination)
        with self.db.transaction():
            row = self._owned(claim)
            if row['redirects'] >= 3:
                raise FrontierError('Too many document redirects; the crawl attempt stopped safely.')
            self.db.execute('UPDATE crawl_urls SET resume_url=?,redirects=redirects+1 WHERE workspace=? AND url=? AND token=?',
                            (destination, self.workspace_id, claim.url, claim.token))

    def retry(self, claim: Claim, error: str, *, until: float | None = None, request_url: str = '') -> None:
        if request_url:
            request_url = self.validate(request_url)
        now = self.now()
        with self.db.transaction():
            row = self._owned(claim)
            failures = row['failures'] + (until is None)
            due = until if until is not None else now + min(86400, 60*2**min(failures-1, 11))
            if not math.isfinite(due) or due < 0:
                raise FrontierError('Retry time must be a finite nonnegative timestamp.')
            due = max(now, due)
            self.db.execute("UPDATE crawl_urls SET state='ready',failures=?,last_error=?,next_due=?,token='',lease_until=0,resume_url=?,redirects=? WHERE workspace=? AND url=? AND token=?",
                            (failures, str(error)[:500], due, (request_url or row['resume_url']) if until is not None else '',
                             row['redirects'] if until is not None else 0, self.workspace_id, claim.url, claim.token))
            self._release(claim)

    def close(self) -> None:
        self.db.close()
