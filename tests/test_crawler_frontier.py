from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.crawler_frontier import CrawlFrontier
from offsetx_apollo_builder.discovery import (
    BLOCKED_SOCIAL_DOMAINS,
    CrawlPolicy,
    DiscoveryFetchError,
    ParsedPage,
    PublicWebCrawler,
    SafePublicFetcher,
    validate_public_url,
)


def _page(url: str, *, links: list[str] | None = None, digest: str = "a" * 64) -> ParsedPage:
    return ParsedPage(
        url=url,
        title=url,
        text="public",
        links=links or [],
        people=[],
        content_sha256=digest,
    )


class RecordingFetcher:
    def __init__(self, *, links: dict[str, list[str]] | None = None):
        self.calls: list[str] = []
        self.links = links or {}

    def fetch(self, url: str) -> ParsedPage:
        self.calls.append(url)
        digest = ("b" if url.endswith("/two") else "a") * 64
        return _page(url, links=self.links.get(url, []), digest=digest)


def test_frontier_honours_robots_and_crawl_delay(monkeypatch):
    policy = CrawlPolicy(allowed_domains=("example.com",), request_delay_seconds=0)
    parser = SimpleNamespace(parse=lambda content, url: _page(url))
    fetcher = SafePublicFetcher(policy, parser=parser)
    delays: list[tuple[str, float]] = []

    def request_bytes(url: str, **_: object):
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nCrawl-delay: 7\nDisallow: /private\n", url, 200
        return b"<html></html>", url, 200

    monkeypatch.setattr(fetcher, "_request_bytes", request_bytes)
    monkeypatch.setattr(
        fetcher,
        "_delay",
        lambda host, extra_delay=0: delays.append((host, float(extra_delay))),
    )

    assert fetcher.fetch("https://example.com/public").url == "https://example.com/public"
    assert ("example.com", 7.0) in delays
    with pytest.raises(DiscoveryFetchError, match="robots.txt disallows"):
        fetcher.fetch("https://example.com/private")
    fetcher.close()


def test_frontier_visits_stable_pages_less_often_than_recent_changes(tmp_path):
    validator = lambda value: validate_public_url(
        value, allowed_domains=("example.com",)
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = start + timedelta(days=120)
    with CrawlFrontier(tmp_path / "frontier.sqlite3", validator=validator) as frontier:
        frontier.admit("https://example.com/stable", 0, now=start)
        frontier.record_success(
            "https://example.com/stable", "a" * 64, observed_at=start
        )
        stable = frontier.record_success(
            "https://example.com/stable", "a" * 64, observed_at=now
        )

        recent_start = now - timedelta(days=2)
        frontier.admit("https://example.com/recent", 0, now=recent_start)
        frontier.record_success(
            "https://example.com/recent", "a" * 64, observed_at=recent_start
        )
        recent = frontier.record_success(
            "https://example.com/recent",
            "b" * 64,
            observed_at=now - timedelta(days=1),
        )

    stable_due = datetime.fromisoformat(stable.next_due_at)
    recent_due = datetime.fromisoformat(recent.next_due_at)
    assert stable_due - now == timedelta(days=30)
    assert recent_due - (now - timedelta(days=1)) == timedelta(days=1)
    assert stable_due > recent_due


def test_frontier_persists_budget_and_does_not_recrawl_not_due_seed(tmp_path):
    path = tmp_path / "frontier.sqlite3"
    policy = CrawlPolicy(
        allowed_domains=("example.com",),
        max_pages=1,
        max_depth=0,
        request_delay_seconds=0,
    )
    first_fetcher = RecordingFetcher()
    first = PublicWebCrawler(policy, first_fetcher, frontier_path=path).crawl(
        ["https://example.com/one", "https://example.com/two"]
    )
    assert len(first.pages) == 1
    assert len(first_fetcher.calls) == 1

    second_fetcher = RecordingFetcher()
    second = PublicWebCrawler(policy, second_fetcher, frontier_path=path).crawl(
        ["https://example.com/one", "https://example.com/two"]
    )
    assert len(second.pages) == 1
    assert len(second_fetcher.calls) == 1
    assert second_fetcher.calls[0] != first_fetcher.calls[0]


def test_frontier_lease_prevents_two_workers_claiming_the_same_url(tmp_path):
    path = tmp_path / "frontier.sqlite3"
    validator = lambda value: validate_public_url(
        value, allowed_domains=("example.com",)
    )
    first = CrawlFrontier(path, validator=validator)
    second = CrawlFrontier(path, validator=validator)
    try:
        first.admit("https://example.com/work", 0)
        claimed = first.claim_due(
            allowed_domains=("example.com",), max_depth=0, limit=1
        )
        duplicate = second.claim_due(
            allowed_domains=("example.com",), max_depth=0, limit=1
        )
        assert [entry.url for entry in claimed] == ["https://example.com/work"]
        assert duplicate == []
    finally:
        first.close()
        second.close()



def test_claim_due_removes_a_persisted_url_rejected_by_current_policy(tmp_path):
    path = tmp_path / "frontier.sqlite3"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with CrawlFrontier(path, validator=lambda value: value) as frontier:
        frontier.admit("https://blocked.example/a", 0, now=now)
        frontier.admit("https://valid.example/b", 0, now=now)

    def current_policy(value: str) -> str:
        if "blocked.example" in value:
            raise ValueError("blocked by current policy")
        return value

    with CrawlFrontier(path, validator=current_policy) as frontier:
        claimed = frontier.claim_due(
            allowed_domains=(),
            max_depth=0,
            limit=1,
            now=now,
        )
        remaining = [entry.url for entry in frontier.snapshot()]

    assert [entry.url for entry in claimed] == ["https://valid.example/b"]
    assert claimed[0].lease_until
    assert "https://blocked.example/a" not in remaining
    assert "https://valid.example/b" in remaining


def test_frontier_never_admits_session_gated_platforms(tmp_path):
    path = tmp_path / "frontier.sqlite3"
    seed = "https://example.com/"
    fetcher = RecordingFetcher(
        links={
            seed: [
                "https://example.com/about",
                "https://www.linkedin.com/in/private-session",
                "https://instagram.com/private-session",
            ]
        }
    )
    policy = CrawlPolicy(
        # Deliberately include the social domains in the allow-list. The
        # session-gated block must win even over operator allow-list input.
        allowed_domains=("example.com", "linkedin.com", "instagram.com"),
        max_pages=1,
        max_depth=1,
        request_delay_seconds=0,
    )
    PublicWebCrawler(policy, fetcher, frontier_path=path).crawl([seed])

    validator = lambda value: validate_public_url(
        value, blocked_domains=BLOCKED_SOCIAL_DOMAINS
    )
    with CrawlFrontier(path, validator=validator) as frontier:
        urls = [entry.url for entry in frontier.snapshot()]

    assert seed in urls
    assert "https://example.com/about" in urls
    assert all("linkedin.com" not in url and "instagram.com" not in url for url in urls)


def test_frontier_spaces_different_urls_on_same_host_across_crawler_processes(
    tmp_path, monkeypatch
):
    path = tmp_path / "frontier.sqlite3"
    policy = CrawlPolicy(
        allowed_domains=("example.com",),
        max_pages=1,
        max_depth=0,
        request_delay_seconds=0,
    )
    waits: list[float] = []
    monkeypatch.setattr(
        "offsetx_apollo_builder.crawler_frontier.time.sleep",
        lambda seconds: waits.append(float(seconds)),
    )

    class PacedFetcher:
        def __init__(self) -> None:
            self.pacer = None

        def set_host_pacer(self, pacer):
            self.pacer = pacer

        def fetch(self, url: str) -> ParsedPage:
            assert self.pacer is not None
            self.pacer("example.com", 0.08)
            return _page(url)

    first = PublicWebCrawler(policy, PacedFetcher(), frontier_path=path)
    first.crawl(["https://example.com/one"])

    second = PublicWebCrawler(policy, PacedFetcher(), frontier_path=path)
    second.crawl(["https://example.com/two"])

    assert len(waits) == 1
    assert waits[0] >= 0.06

