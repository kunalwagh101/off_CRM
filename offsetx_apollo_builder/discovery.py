"""Guarded public-web POI discovery, research memory and Apollo hand-off.

The lightweight engine uses Requests plus Scrapling. The optional JavaScript
engine uses Crawl4AI in standard headless mode. Neither engine enables stealth,
CAPTCHA/Cloudflare bypass, logged-in cookies, proxies, persistent profiles or
platform-specific anti-bot evasion. LinkedIn, Instagram and similar social
domains remain blocked crawl targets; official API adapters can feed the same
normalized research graph later.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import ipaddress
import json
import os
import re
import socket
import tempfile
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

from .dedupe import (
    ExclusionSet,
    build_exclusion_set,
    discover_exclusion_files,
    name_company_key,
    norm_email,
    norm_linkedin,
    norm_text,
)
from .locked_categories import DEFAULT_CATEGORY, normalize_category
from .outreach.email_expert import route_for_category
from .outreach.models import ContactInput, clean_text, stable_identity_key
from .outreach.store import OutreachStore
from .research import (
    DiscoveryPlan,
    compile_discovery_plan,
    normalized_social_handles,
    objective_match,
    social_platform,
)


BLOCKED_SOCIAL_DOMAINS = (
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "threads.net",
    "tiktok.com",
    "twitter.com",
    "x.com",
)
SKIPPED_FILE_SUFFIXES = {
    ".7z",
    ".avi",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".jpg",
    ".jpeg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".rar",
    ".svg",
    ".tar",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


class DiscoveryFetchError(RuntimeError):
    """A page could not be fetched under the configured safety policy."""


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def normalize_domain(value: str) -> str:
    text = clean_text(value).lower().rstrip(".")
    if "://" in text:
        text = urlsplit(text).hostname or ""
    return text.removeprefix("www.").encode("idna").decode("ascii")


def canonical_url(value: str) -> str:
    parsed = urlsplit(clean_text(value))
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if not scheme or not host:
        return clean_text(value)
    port = parsed.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def validate_public_url(
    value: str,
    *,
    allowed_domains: Sequence[str] = (),
    blocked_domains: Sequence[str] = BLOCKED_SOCIAL_DOMAINS,
) -> str:
    """Validate syntax and domain policy without making a network request."""
    supplied = urlsplit(clean_text(value))
    if supplied.username or supplied.password:
        raise ValueError("Discovery URLs cannot contain credentials")
    url = canonical_url(value)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Discovery URLs must use http or https")
    host = normalize_domain(parsed.hostname or "")
    if not host or host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Discovery URL must use a public hostname")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private, local and reserved network addresses are blocked")
    denied = tuple(normalize_domain(item) for item in blocked_domains if normalize_domain(item))
    if any(_host_matches(host, domain) for domain in denied):
        raise ValueError(
            f"Automated crawling is disabled for {host}; use an official API or manual import"
        )
    allowed = tuple(normalize_domain(item) for item in allowed_domains if normalize_domain(item))
    if allowed and not any(_host_matches(host, domain) for domain in allowed):
        raise ValueError(f"Domain {host} is outside this run's allow-list")
    return url


@dataclass(frozen=True, slots=True)
class CrawlPolicy:
    allowed_domains: tuple[str, ...]
    max_pages: int = 20
    max_depth: int = 1
    obey_robots: bool = True
    request_delay_seconds: float = 0.75
    timeout_seconds: int = 20
    max_html_bytes: int = 2_000_000
    user_agent: str = "OffsetXPublicResearchBot/0.9"
    blocked_domains: tuple[str, ...] = BLOCKED_SOCIAL_DOMAINS
    parallel_workers: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.parallel_workers <= 4:
            raise ValueError("parallel_workers must be between 1 and 4")
        if not 1 <= self.max_pages <= 100:
            raise ValueError("max_pages must be between 1 and 100")
        if not 0 <= self.max_depth <= 3:
            raise ValueError("max_depth must be between 0 and 3")
        if not 0 <= self.request_delay_seconds <= 30:
            raise ValueError("request delay must be between 0 and 30 seconds")
        if not 5 <= self.timeout_seconds <= 60:
            raise ValueError("timeout must be between 5 and 60 seconds")
        if not self.allowed_domains:
            raise ValueError("At least one allowed domain is required")


@dataclass(slots=True)
class DiscoveredPerson:
    full_name: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    company: str = ""
    company_domain: str = ""
    title: str = ""
    country: str = ""
    linkedin_url: str = ""
    public_hook: str = ""
    confidence: float = 0.5
    social_handles: dict[str, list[str]] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedPage:
    url: str
    title: str
    text: str
    links: list[str]
    people: list[DiscoveredPerson]
    content_sha256: str


class PageFetcher(Protocol):
    def fetch(self, url: str) -> ParsedPage: ...


def _schema_type_is_person(value: Any) -> bool:
    values = value if isinstance(value, list) else [value]
    return any(str(item).lower().rsplit("/", 1)[-1] == "person" for item in values)


def _value_name(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("name") or value.get("legalName"))
    if isinstance(value, list):
        return next((_value_name(item) for item in value if _value_name(item)), "")
    return clean_text(value)


def _iter_json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _iter_json_objects(item)
    elif isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph is not None:
            yield from _iter_json_objects(graph)


def _first_url(value: Any, needle: str = "") -> str:
    values = value if isinstance(value, list) else [value]
    for item in values:
        url = clean_text(item.get("url") if isinstance(item, dict) else item)
        if url and (not needle or needle in url.lower()):
            return url
    return ""


def _country_from(value: Any) -> str:
    if isinstance(value, dict):
        address = value.get("address") if isinstance(value.get("address"), dict) else value
        return _value_name(address.get("addressCountry") or address.get("country"))
    return ""


def _person_from_jsonld(item: dict[str, Any], page_title: str) -> DiscoveredPerson | None:
    if not _schema_type_is_person(item.get("@type")):
        return None
    full_name = _value_name(item.get("name"))
    first_name = _value_name(item.get("givenName"))
    last_name = _value_name(item.get("familyName"))
    if not full_name:
        full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        return None
    if full_name and not first_name:
        parts = full_name.split()
        first_name = parts[0]
        last_name = " ".join(parts[1:])

    organization = item.get("worksFor") or item.get("affiliation") or item.get("memberOf")
    company = _value_name(organization)
    company_url = _first_url(organization)
    company_domain = normalize_domain(company_url) if company_url else ""
    title = _value_name(item.get("jobTitle") or item.get("hasOccupation"))
    same_as = item.get("sameAs") or []
    linkedin_url = _first_url(same_as, "linkedin.com/")
    social_handles = normalized_social_handles(same_as if isinstance(same_as, list) else [same_as])
    email = _value_name(item.get("email")).removeprefix("mailto:").lower()
    description = clean_text(item.get("description") or item.get("disambiguatingDescription"))
    if description:
        public_hook = description[:800]
    elif title and company:
        public_hook = f"{full_name} is publicly listed as {title} at {company}."
    elif page_title:
        public_hook = f"{full_name} is publicly listed on {page_title}."
    else:
        public_hook = ""
    country = _country_from(item.get("homeLocation") or item.get("address"))
    signals = sum(bool(value) for value in (title, company, linkedin_url, email, description))
    confidence = min(0.98, 0.55 + signals * 0.08)
    return DiscoveredPerson(
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        company=company,
        company_domain=company_domain,
        title=title,
        country=country,
        linkedin_url=linkedin_url,
        public_hook=public_hook,
        confidence=round(confidence, 2),
        social_handles=social_handles,
        evidence={
            "format": "schema_org_person",
            "name": full_name,
            "job_title": title,
            "organization": company,
            "description": description[:1000],
            "social_handles": social_handles,
        },
    )


class ScraplingPageParser:
    """Parse bounded HTML with Scrapling's selector engine, without its stealth fetchers."""

    def __init__(self) -> None:
        try:
            from scrapling.parser import Selector
        except ImportError as exc:  # pragma: no cover - deployment configuration guard
            raise RuntimeError(
                "Scrapling is not installed. Install the project dependencies and retry."
            ) from exc
        self.selector_class = Selector

    def parse(self, content: bytes, url: str) -> ParsedPage:
        page = self.selector_class(
            content=content,
            url=url,
            encoding="utf-8",
            huge_tree=False,
            adaptive=False,
        )
        title = clean_text(page.css("title::text").get() or "")[:500]
        bodies = page.css("body")
        text = clean_text(str(bodies[0].get_all_text(separator=" ", strip=True))) if bodies else ""
        links: list[str] = []
        for raw in page.css("a::attr(href)").getall():
            candidate = clean_text(raw)
            if not candidate or candidate.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            joined = canonical_url(urljoin(url, candidate))
            if joined not in links:
                links.append(joined)

        people: list[DiscoveredPerson] = []
        for raw in page.css('script[type="application/ld+json"]::text').getall():
            try:
                payload = json.loads(str(raw).strip())
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            for item in _iter_json_objects(payload):
                person = _person_from_jsonld(item, title)
                if person:
                    people.append(person)
        return ParsedPage(
            url=url,
            title=title,
            text=text[:100_000],
            links=links,
            people=people,
            content_sha256=hashlib.sha256(content).hexdigest(),
        )


class SafePublicFetcher:
    """Fetch public HTML with SSRF, robots, size, redirect and rate-limit guards."""

    def __init__(
        self,
        policy: CrawlPolicy,
        *,
        session: requests.Session | None = None,
        parser: ScraplingPageParser | None = None,
        resolver: Callable[..., Any] = socket.getaddrinfo,
    ) -> None:
        self.policy = policy
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.parser = parser or ScraplingPageParser()
        self.resolver = resolver
        self.robots: dict[str, tuple[RobotFileParser, float]] = {}
        self.last_request_at: dict[str, float] = {}

    def _assert_public_dns(self, url: str) -> None:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        try:
            addresses = [ipaddress.ip_address(host.strip("[]"))]
        except ValueError:
            try:
                resolved = self.resolver(
                    host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
                )
            except OSError as exc:
                raise DiscoveryFetchError(f"DNS lookup failed for {host}") from exc
            addresses = []
            for item in resolved:
                try:
                    addresses.append(ipaddress.ip_address(item[4][0]))
                except (ValueError, IndexError):
                    continue
        if not addresses or any(not address.is_global for address in addresses):
            raise DiscoveryFetchError("Private, local and reserved network targets are blocked")

    def _delay(self, host: str, extra_delay: float = 0) -> None:
        delay = max(self.policy.request_delay_seconds, extra_delay)
        remaining = self.last_request_at.get(host, 0) + delay - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)
        self.last_request_at[host] = time.monotonic()

    def _request_bytes(
        self, url: str, *, max_bytes: int, accepted_types: Sequence[str]
    ) -> tuple[bytes, str, int]:
        current = url
        for _ in range(4):
            current = validate_public_url(
                current,
                allowed_domains=self.policy.allowed_domains,
                blocked_domains=self.policy.blocked_domains,
            )
            self._assert_public_dns(current)
            host = normalize_domain(urlsplit(current).hostname or "")
            self._delay(host)
            self.session.cookies.clear()
            response = self.session.get(
                current,
                headers={
                    "User-Agent": self.policy.user_agent,
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
                },
                timeout=self.policy.timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
            try:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location", "")
                    if not location:
                        raise DiscoveryFetchError("Redirect response did not include a location")
                    current = urljoin(current, location)
                    continue
                if response.status_code == 404:
                    return b"", current, 404
                if response.status_code != 200:
                    raise DiscoveryFetchError(f"HTTP {response.status_code} while fetching public page")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if content_type and not any(
                    content_type == item or content_type.startswith(item.rstrip("*") )
                    for item in accepted_types
                ):
                    raise DiscoveryFetchError(f"Unsupported content type: {content_type}")
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise DiscoveryFetchError("Public page exceeded the configured size limit")
                    chunks.append(chunk)
                return b"".join(chunks), current, 200
            finally:
                response.close()
                self.session.cookies.clear()
        raise DiscoveryFetchError("Too many redirects")

    def _robots_allowed(self, url: str) -> tuple[bool, float]:
        host = normalize_domain(urlsplit(url).hostname or "")
        cached = self.robots.get(host)
        if cached is None:
            parsed = urlsplit(url)
            robots_url = urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
            try:
                content, _, status = self._request_bytes(
                    robots_url,
                    max_bytes=256_000,
                    accepted_types=("text/plain", "text/*", "text/html", ""),
                )
            except DiscoveryFetchError as exc:
                raise DiscoveryFetchError("robots.txt could not be verified; crawl stopped safely") from exc
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(content.decode("utf-8", errors="replace").splitlines() if status == 200 else [])
            delay = min(30.0, float(parser.crawl_delay(self.policy.user_agent) or 0))
            cached = (parser, delay)
            self.robots[host] = cached
        parser, delay = cached
        return parser.can_fetch(self.policy.user_agent, url), delay

    def fetch(self, url: str) -> ParsedPage:
        validated = validate_public_url(
            url,
            allowed_domains=self.policy.allowed_domains,
            blocked_domains=self.policy.blocked_domains,
        )
        if self.policy.obey_robots:
            allowed, robots_delay = self._robots_allowed(validated)
            if not allowed:
                raise DiscoveryFetchError("robots.txt disallows this page")
            host = normalize_domain(urlsplit(validated).hostname or "")
            self._delay(host, robots_delay)
        content, final_url, status = self._request_bytes(
            validated,
            max_bytes=self.policy.max_html_bytes,
            accepted_types=("text/html", "application/xhtml+xml"),
        )
        if status != 200:
            raise DiscoveryFetchError("Public page was not found")
        return self.parser.parse(content, final_url)

    def close(self) -> None:
        self.session.close()


class Crawl4AIPageFetcher:
    """Render public JavaScript pages with Crawl4AI under the same safety policy.

    This adapter intentionally fixes every evasive option to ``False`` and does
    not accept user-provided browser settings. Browser routes are checked for
    public DNS targets, while document navigations must remain inside the run's
    explicit domain allow-list.
    """

    def __init__(
        self,
        policy: CrawlPolicy,
        *,
        parser: ScraplingPageParser | None = None,
        resolver: Callable[..., Any] = socket.getaddrinfo,
        base_directory: Path | None = None,
    ) -> None:
        runtime_root = Path(base_directory or tempfile.gettempdir())
        runtime_root.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(runtime_root))
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
        except ImportError as exc:  # pragma: no cover - optional deployment path
            raise RuntimeError(
                "Crawl4AI is not installed. Install the crawler extra and Chromium first."
            ) from exc
        self.policy = policy
        self.parser = parser or ScraplingPageParser()
        self.guard = SafePublicFetcher(policy, parser=self.parser, resolver=resolver)
        self._loop = asyncio.new_event_loop()
        self._crawler = AsyncWebCrawler(
            config=BrowserConfig(
                browser_type="chromium",
                headless=True,
                browser_mode="dedicated",
                use_persistent_context=False,
                accept_downloads=False,
                ignore_https_errors=False,
                java_script_enabled=True,
                cookies=[],
                user_agent=policy.user_agent,
                user_agent_mode="",
                text_mode=True,
                light_mode=True,
                enable_stealth=False,
            )
        )
        self._run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            check_robots_txt=True,
            user_agent=policy.user_agent,
            wait_until="domcontentloaded",
            page_timeout=policy.timeout_seconds * 1000,
            wait_for_images=False,
            process_iframes=False,
            scan_full_page=False,
            remove_overlay_elements=False,
            remove_consent_popups=False,
            simulate_user=False,
            override_navigator=False,
            magic=False,
            screenshot=False,
            pdf=False,
            exclude_all_images=True,
            exclude_social_media_links=False,
            exclude_social_media_domains=list(policy.blocked_domains),
            max_retries=0,
            stream=False,
            verbose=False,
        )
        self._started = False

    async def _assert_route(self, request_url: str, resource_type: str) -> None:
        parsed = urlsplit(request_url)
        if parsed.scheme in {"about", "blob", "data"}:
            return
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Unsupported browser request scheme")
        validate_public_url(
            request_url,
            allowed_domains=self.policy.allowed_domains if resource_type == "document" else (),
            blocked_domains=self.policy.blocked_domains,
        )
        await asyncio.to_thread(self.guard._assert_public_dns, request_url)

    async def _ensure_started(self) -> None:
        if self._started:
            return

        async def on_page_context_created(page: Any, context: Any, **_: Any) -> Any:
            async def route_filter(route: Any) -> None:
                request = route.request
                if request.resource_type in {"image", "media", "font", "websocket"}:
                    await route.abort()
                    return
                try:
                    await self._assert_route(request.url, request.resource_type)
                except (DiscoveryFetchError, ValueError, OSError):
                    await route.abort()
                    return
                await route.continue_()

            await context.route("**/*", route_filter)
            return page

        self._crawler.crawler_strategy.set_hook(
            "on_page_context_created", on_page_context_created
        )
        await self._crawler.start()
        self._started = True

    async def _fetch(self, url: str) -> Any:
        await self._ensure_started()
        return await self._crawler.arun(url=url, config=self._run_config)

    def fetch(self, url: str) -> ParsedPage:
        validated = validate_public_url(
            url,
            allowed_domains=self.policy.allowed_domains,
            blocked_domains=self.policy.blocked_domains,
        )
        self.guard._assert_public_dns(validated)
        if self.policy.obey_robots:
            allowed, robots_delay = self.guard._robots_allowed(validated)
            if not allowed:
                raise DiscoveryFetchError("robots.txt disallows this page")
        else:  # API currently fixes this to True; retained for direct library callers.
            robots_delay = 0
        host = normalize_domain(urlsplit(validated).hostname or "")
        self.guard._delay(host, robots_delay)
        try:
            result = self._loop.run_until_complete(self._fetch(validated))
        except Exception as exc:
            raise DiscoveryFetchError(f"Crawl4AI could not render the public page: {exc}") from exc
        if not getattr(result, "success", False):
            message = clean_text(getattr(result, "error_message", "crawl failed"))
            raise DiscoveryFetchError(message or "Crawl4AI crawl failed")
        final_url = validate_public_url(
            clean_text(getattr(result, "url", "")) or validated,
            allowed_domains=self.policy.allowed_domains,
            blocked_domains=self.policy.blocked_domains,
        )
        self.guard._assert_public_dns(final_url)
        raw_html = getattr(result, "html", "") or ""
        content = raw_html if isinstance(raw_html, bytes) else str(raw_html).encode("utf-8")
        if not content:
            raise DiscoveryFetchError("Crawl4AI returned no HTML")
        if len(content) > self.policy.max_html_bytes:
            raise DiscoveryFetchError("Rendered public page exceeded the configured size limit")
        return self.parser.parse(content, final_url)

    def close(self) -> None:
        try:
            if self._started:
                self._loop.run_until_complete(self._crawler.close())
        finally:
            self.guard.close()
            if not self._loop.is_closed():
                self._loop.close()


@dataclass(slots=True)
class CrawlResult:
    pages: list[ParsedPage] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class DomainRateLimiter:
    """Shared politeness gate: one request per domain per delay window.

    Parallel workers coordinate through this limiter so raising the worker
    count never raises the request rate against any single site.
    """

    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(0.0, float(delay_seconds))
        self._lock = threading.Lock()
        self._domain_locks: dict[str, threading.Lock] = {}
        self._last_hit: dict[str, float] = {}

    def _domain_lock(self, domain: str) -> threading.Lock:
        with self._lock:
            lock = self._domain_locks.get(domain)
            if lock is None:
                lock = threading.Lock()
                self._domain_locks[domain] = lock
            return lock

    def wait_turn(self, url: str) -> None:
        domain = normalize_domain(urlsplit(url).hostname or "")
        if not domain:
            return
        with self._domain_lock(domain):
            now = time.monotonic()
            wait = self._last_hit.get(domain, 0.0) + self.delay_seconds - now
            if wait > 0:
                time.sleep(wait)
            self._last_hit[domain] = time.monotonic()


class PublicWebCrawler:
    def __init__(
        self,
        policy: CrawlPolicy,
        fetcher: PageFetcher,
        *,
        fetcher_factory: Callable[[], PageFetcher] | None = None,
    ) -> None:
        self.policy = policy
        self.fetcher = fetcher
        self.fetcher_factory = fetcher_factory
        self.rate_limiter = DomainRateLimiter(policy.request_delay_seconds)

    def _validated_seed_queue(
        self, seed_urls: Sequence[str]
    ) -> tuple[deque[tuple[str, int]], set[str]]:
        queue: deque[tuple[str, int]] = deque()
        queued: set[str] = set()
        for seed in seed_urls:
            url = validate_public_url(
                seed,
                allowed_domains=self.policy.allowed_domains,
                blocked_domains=self.policy.blocked_domains,
            )
            if url not in queued:
                queue.append((url, 0))
                queued.add(url)
        return queue, queued

    def _enqueue_links(
        self,
        page: ParsedPage,
        depth: int,
        queue: deque[tuple[str, int]],
        queued: set[str],
        seen: set[str],
    ) -> None:
        if depth >= self.policy.max_depth:
            return
        for link in page.links:
            path = urlsplit(link).path.lower()
            if any(path.endswith(suffix) for suffix in SKIPPED_FILE_SUFFIXES):
                continue
            try:
                allowed = validate_public_url(
                    link,
                    allowed_domains=self.policy.allowed_domains,
                    blocked_domains=self.policy.blocked_domains,
                )
            except ValueError:
                continue
            if allowed not in seen and allowed not in queued:
                queue.append((allowed, depth + 1))
                queued.add(allowed)

    def crawl(self, seed_urls: Sequence[str]) -> CrawlResult:
        workers = max(1, int(self.policy.parallel_workers))
        if workers > 1 and self.fetcher_factory is not None:
            return self._crawl_parallel(seed_urls, workers)
        return self._crawl_sequential(seed_urls)

    def _crawl_sequential(self, seed_urls: Sequence[str]) -> CrawlResult:
        result = CrawlResult()
        queue, queued = self._validated_seed_queue(seed_urls)
        seen: set[str] = set()
        try:
            while queue and len(result.pages) < self.policy.max_pages:
                url, depth = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                try:
                    page = self.fetcher.fetch(url)
                except (DiscoveryFetchError, ValueError, requests.RequestException) as exc:
                    result.errors.append({"url": url, "error": clean_text(exc)[:500]})
                    continue
                result.pages.append(page)
                self._enqueue_links(page, depth, queue, queued, seen)
        finally:
            close = getattr(self.fetcher, "close", None)
            if callable(close):
                close()
        return result

    def _crawl_parallel(self, seed_urls: Sequence[str], workers: int) -> CrawlResult:
        """Breadth-first crawl in waves of up to `workers` concurrent fetches.

        Each worker thread owns its own fetcher instance (fetchers keep
        session and event-loop state, so they are never shared). The shared
        DomainRateLimiter keeps the per-domain request rate identical to the
        sequential crawl, so parallelism speeds up multi-domain runs without
        hammering any single site.
        """
        result = CrawlResult()
        queue, queued = self._validated_seed_queue(seed_urls)
        seen: set[str] = set()
        thread_fetchers: dict[int, PageFetcher] = {}
        fetcher_lock = threading.Lock()
        assert self.fetcher_factory is not None

        def fetch_one(url: str) -> ParsedPage:
            ident = threading.get_ident()
            with fetcher_lock:
                fetcher = thread_fetchers.get(ident)
                if fetcher is None:
                    fetcher = self.fetcher_factory()
                    thread_fetchers[ident] = fetcher
            self.rate_limiter.wait_turn(url)
            return fetcher.fetch(url)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                while queue and len(result.pages) < self.policy.max_pages:
                    wave: list[tuple[str, int]] = []
                    budget = self.policy.max_pages - len(result.pages)
                    while queue and len(wave) < min(workers, budget):
                        url, depth = queue.popleft()
                        if url in seen:
                            continue
                        seen.add(url)
                        wave.append((url, depth))
                    if not wave:
                        continue
                    futures = {
                        pool.submit(fetch_one, url): (url, depth) for url, depth in wave
                    }
                    for future in as_completed(futures):
                        url, depth = futures[future]
                        try:
                            page = future.result()
                        except (
                            DiscoveryFetchError,
                            ValueError,
                            requests.RequestException,
                        ) as exc:
                            result.errors.append(
                                {"url": url, "error": clean_text(exc)[:500]}
                            )
                            continue
                        if len(result.pages) < self.policy.max_pages:
                            result.pages.append(page)
                            self._enqueue_links(page, depth, queue, queued, seen)
        finally:
            for fetcher in thread_fetchers.values():
                close = getattr(fetcher, "close", None)
                if callable(close):
                    close()
            close = getattr(self.fetcher, "close", None)
            if callable(close):
                close()
        return result


def _candidate_record(
    person: DiscoveredPerson,
    *,
    page: ParsedPage,
    category: str,
    route: str,
    plan: DiscoveryPlan,
    engine: str,
) -> dict[str, Any]:
    identity_key = stable_identity_key(
        full_name=person.full_name,
        company=person.company,
        title=person.title,
        linkedin_url=person.linkedin_url,
        email=person.email,
    )
    match = objective_match(person.title, person.company, plan)
    confidence = round(min(0.99, person.confidence * 0.8 + match["score"] * 0.2), 2)
    return {
        "identity_key": identity_key,
        "full_name": person.full_name,
        "first_name": person.first_name,
        "last_name": person.last_name,
        "email": person.email,
        "company": person.company,
        "company_domain": person.company_domain,
        "title": person.title,
        "category": category,
        "route": route,
        "country": person.country,
        "linkedin_url": person.linkedin_url,
        "source_url": page.url,
        "public_hook": person.public_hook,
        "confidence": confidence,
        "evidence": {**person.evidence, "objective_match": match},
        "source_data": {
            "engine": engine,
            "parser": "scrapling",
            "public_only": True,
            "page_title": page.title,
            "page_sha256": page.content_sha256,
            "social_handles": person.social_handles,
            "objective_match": match,
        },
    }


def discovery_duplicate(
    exclusion: ExclusionSet, candidate: dict[str, Any]
) -> tuple[bool, str]:
    """Use person-level keys so two people with the same company/title survive."""
    email = norm_email(candidate.get("email"))
    if email and email in exclusion.emails:
        return True, "duplicate_email"
    linkedin = norm_linkedin(candidate.get("linkedin_url"))
    if linkedin and linkedin in exclusion.linkedin_urls:
        return True, "duplicate_linkedin"
    full_name = norm_text(candidate.get("name") or candidate.get("full_name"))
    company = norm_text(candidate.get("company") or candidate.get("organization_name"))
    if full_name and company and name_company_key(full_name, company) in exclusion.name_company_pairs:
        return True, "duplicate_name_company"
    return False, "fresh"


class DiscoveryService:
    def __init__(
        self,
        store: OutreachStore,
        *,
        project_root: Path,
        data_dir: Path,
        fetcher_factory: Callable[[CrawlPolicy], PageFetcher] | None = None,
    ) -> None:
        self.store = store
        self.project_root = Path(project_root)
        self.data_dir = Path(data_dir)
        self.fetcher_factory = fetcher_factory

    def _fetcher(self, policy: CrawlPolicy, engine: str) -> PageFetcher:
        if self.fetcher_factory is not None:
            return self.fetcher_factory(policy)
        if engine == "safe_http":
            return SafePublicFetcher(policy)
        if engine == "crawl4ai_public_js":
            return Crawl4AIPageFetcher(
                policy,
                base_directory=self.data_dir / "crawler_runtime",
            )
        raise ValueError("Discovery engine must be safe_http or crawl4ai_public_js")

    def _exclusions(self) -> ExclusionSet:
        paths = discover_exclusion_files(
            exclusion_dir=self.project_root / "old_pois",
            include_previous_outputs=True,
            project_root=self.project_root,
        )
        data_old_pois = self.data_dir / "old_pois"
        if data_old_pois.exists():
            paths.extend(
                discover_exclusion_files(
                    exclusion_dir=data_old_pois,
                    include_previous_outputs=False,
                    project_root=self.project_root,
                )
            )
        unique = list({str(path.resolve()): path for path in paths}.values())
        exclusion = build_exclusion_set(unique)
        for row in self.store.contact_exclusion_records():
            exclusion.add_record(row)
        return exclusion

    def run(
        self,
        *,
        campaign_id: str,
        seed_urls: Sequence[str],
        allowed_domains: Sequence[str] = (),
        category: str = DEFAULT_CATEGORY,
        max_pages: int = 20,
        max_depth: int = 1,
        obey_robots: bool = True,
        request_delay_seconds: float = 0.75,
        engine: str = "safe_http",
        objective_prompt: str = "",
        target_count: int = 100,
        parallel_workers: int = 1,
    ) -> dict[str, Any]:
        if not seed_urls:
            raise ValueError("At least one public seed URL is required")
        domains = [normalize_domain(item) for item in allowed_domains if normalize_domain(item)]
        if not domains:
            domains = [normalize_domain(urlsplit(item).hostname or "") for item in seed_urls]
        domains = list(dict.fromkeys(item for item in domains if item))
        normalized_category = normalize_category(category, default=DEFAULT_CATEGORY)
        route = route_for_category(normalized_category)
        if engine not in {"safe_http", "crawl4ai_public_js"}:
            raise ValueError("Discovery engine must be safe_http or crawl4ai_public_js")
        plan = compile_discovery_plan(
            objective_prompt,
            default_target_count=target_count,
        )
        policy = CrawlPolicy(
            allowed_domains=tuple(domains),
            max_pages=max_pages,
            max_depth=max_depth,
            obey_robots=obey_robots,
            request_delay_seconds=request_delay_seconds,
            parallel_workers=parallel_workers,
        )
        stored_plan = plan.to_dict()
        stored_plan["parallel_workers"] = policy.parallel_workers
        validated_seeds = [
            validate_public_url(
                item,
                allowed_domains=policy.allowed_domains,
                blocked_domains=policy.blocked_domains,
            )
            for item in seed_urls
        ]
        run_id = self.store.create_discovery_run(
            campaign_id=campaign_id,
            seed_urls=validated_seeds,
            allowed_domains=domains,
            category=normalized_category,
            route=route,
            max_pages=max_pages,
            max_depth=max_depth,
            obey_robots=obey_robots,
            engine=engine,
            objective_prompt=plan.objective,
            plan=stored_plan,
            target_count=plan.target_count,
        )
        try:
            crawl = PublicWebCrawler(
                policy,
                self._fetcher(policy, engine),
                fetcher_factory=lambda: self._fetcher(policy, engine),
            ).crawl(validated_seeds)
            exclusion = self._exclusions()
            seen: set[str] = set()
            fresh = 0
            excluded = 0
            found = 0
            target_reached = False
            for page in crawl.pages:
                for person in page.people:
                    record = _candidate_record(
                        person,
                        page=page,
                        category=normalized_category,
                        route=route,
                        plan=plan,
                        engine=engine,
                    )
                    if record["identity_key"] in seen:
                        continue
                    seen.add(record["identity_key"])
                    duplicate, reason = discovery_duplicate(
                        exclusion,
                        {
                            "name": record["full_name"],
                            "email": record["email"],
                            "company": record["company"],
                            "title": record["title"],
                            "linkedin_url": record["linkedin_url"],
                        }
                    )
                    record["status"] = "excluded" if duplicate else "new"
                    record["exclusion_reason"] = reason if duplicate else ""
                    candidate_id = self.store.add_discovery_candidate(run_id, record)
                    self._remember_candidate(
                        run_id=run_id,
                        candidate_id=candidate_id,
                        record=record,
                    )
                    found += 1
                    if duplicate:
                        excluded += 1
                    else:
                        fresh += 1
                        exclusion.add_record(
                            {
                                "name": record["full_name"],
                                "email": record["email"],
                                "company": record["company"],
                                "title": record["title"],
                                "linkedin_url": record["linkedin_url"],
                            }
                        )
                        if fresh >= plan.target_count:
                            target_reached = True
                            break
                if target_reached:
                    break
            status = "completed" if crawl.pages and not crawl.errors else "partial"
            if not crawl.pages:
                status = "failed"
            return self.store.finish_discovery_run(
                run_id,
                status=status,
                pages_crawled=len(crawl.pages),
                candidates_found=found,
                fresh_count=fresh,
                excluded_count=excluded,
                errors=crawl.errors,
            )
        except Exception as exc:
            self.store.finish_discovery_run(
                run_id,
                status="failed",
                pages_crawled=0,
                candidates_found=0,
                fresh_count=0,
                excluded_count=0,
                errors=[{"error": clean_text(exc)[:500]}],
            )
            raise

    def _remember_candidate(
        self,
        *,
        run_id: str,
        candidate_id: str,
        record: dict[str, Any],
    ) -> None:
        """Add de-duplicated public facts to the local research graph.

        Email addresses are deliberately omitted from graph properties so this
        context layer cannot accidentally become a copy of Gmail or a provider
        payload containing unrelated mailbox data.
        """
        source_url = canonical_url(record["source_url"])
        person_id = self.store.upsert_research_entity(
            entity_type="person",
            canonical_key=record["identity_key"],
            name=record["full_name"],
            properties={
                "title": record["title"],
                "country": record["country"],
                "category": record["category"],
                "public_hook": record["public_hook"],
            },
            confidence=record["confidence"],
        )
        page_id = self.store.upsert_research_entity(
            entity_type="source_page",
            canonical_key=source_url,
            name=record["source_data"].get("page_title") or source_url,
            properties={
                "url": source_url,
                "content_sha256": record["source_data"].get("page_sha256", ""),
                "public_only": True,
            },
            confidence=1.0,
        )
        self.store.upsert_research_edge(
            source_entity_id=person_id,
            target_entity_id=page_id,
            relation_type="MENTIONED_ON",
            confidence=record["confidence"],
            evidence_url=source_url,
        )
        self.store.add_research_observation(
            entity_id=person_id,
            source_url=source_url,
            evidence=record["evidence"],
            run_id=run_id,
            candidate_id=candidate_id,
        )
        self.store.add_research_observation(
            entity_id=page_id,
            source_url=source_url,
            evidence={"page_sha256": record["source_data"].get("page_sha256", "")},
            run_id=run_id,
            candidate_id=candidate_id,
        )

        if record["company"]:
            company_key = normalize_domain(record["company_domain"]) or norm_text(record["company"])
            company_id = self.store.upsert_research_entity(
                entity_type="company",
                canonical_key=company_key,
                name=record["company"],
                properties={"domain": normalize_domain(record["company_domain"])},
                confidence=record["confidence"],
            )
            self.store.upsert_research_edge(
                source_entity_id=person_id,
                target_entity_id=company_id,
                relation_type="WORKS_AT",
                properties={"title": record["title"]},
                confidence=record["confidence"],
                evidence_url=source_url,
            )
            self.store.add_research_observation(
                entity_id=company_id,
                source_url=source_url,
                evidence={"name": record["company"], "domain": record["company_domain"]},
                run_id=run_id,
                candidate_id=candidate_id,
            )

        social_handles = record["source_data"].get("social_handles") or {}
        for platform, urls in social_handles.items():
            for profile_url in urls:
                profile_id = self.store.upsert_research_entity(
                    entity_type="social_profile",
                    canonical_key=canonical_url(profile_url),
                    name=f"{record['full_name']} on {platform}",
                    properties={
                        "platform": platform,
                        "url": canonical_url(profile_url),
                        "access_mode": "reference_only",
                    },
                    confidence=record["confidence"],
                )
                self.store.upsert_research_edge(
                    source_entity_id=person_id,
                    target_entity_id=profile_id,
                    relation_type="HAS_SOCIAL_PROFILE",
                    properties={"platform": platform, "not_crawled": True},
                    confidence=record["confidence"],
                    evidence_url=source_url,
                )
                self.store.add_research_observation(
                    entity_id=profile_id,
                    source_url=source_url,
                    evidence={"platform": platform, "url": profile_url},
                    run_id=run_id,
                    candidate_id=candidate_id,
                )

    def research_graph(self, *, run_id: str = "", query: str = "", limit: int = 250) -> dict[str, Any]:
        return self.store.research_graph(run_id=run_id, query=query, limit=limit)

    def record_social_interaction(
        self,
        *,
        actor_name: str,
        actor_handle: str,
        target_name: str,
        target_handle: str,
        platform: str,
        interaction_type: str,
        source_url: str,
        observed_at: str = "",
        source_type: str = "manual_import",
        rights_basis: str = "public_evidence",
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        platform = clean_text(platform).lower()
        interaction_type = clean_text(interaction_type).upper()
        if source_type not in {"manual_import", "official_api"}:
            raise ValueError("Interaction source must be manual_import or official_api")
        if not rights_basis:
            raise ValueError("A rights basis is required for interaction evidence")
        evidence_url = validate_public_url(source_url, blocked_domains=())
        actor_url = validate_public_url(actor_handle, blocked_domains=())
        target_url = validate_public_url(target_handle, blocked_domains=())
        if platform == "":
            platform = social_platform(actor_url)
        actor_id = self.store.upsert_research_entity(
            entity_type="social_profile",
            canonical_key=canonical_url(actor_url),
            name=clean_text(actor_name) or actor_url,
            properties={"platform": platform, "url": actor_url, "access_mode": source_type},
            confidence=1.0,
        )
        target_id = self.store.upsert_research_entity(
            entity_type="social_profile",
            canonical_key=canonical_url(target_url),
            name=clean_text(target_name) or target_url,
            properties={"platform": platform, "url": target_url, "access_mode": source_type},
            confidence=1.0,
        )
        edge_id = self.store.upsert_research_edge(
            source_entity_id=actor_id,
            target_entity_id=target_id,
            relation_type="INTERACTED_WITH",
            properties={
                "platform": platform,
                "interaction_type": interaction_type,
                "observed_at": clean_text(observed_at),
                "source_type": source_type,
                "rights_basis": clean_text(rights_basis),
                "evidence": evidence or {},
            },
            confidence=1.0,
            evidence_url=evidence_url,
        )
        self.store.add_research_observation(
            entity_id=actor_id,
            source_url=evidence_url,
            evidence={
                "target": target_url,
                "interaction_type": interaction_type,
                "source_type": source_type,
                "rights_basis": rights_basis,
                **(evidence or {}),
            },
        )
        return {"edge_id": edge_id, "actor_entity_id": actor_id, "target_entity_id": target_id}

    def decide(self, run_id: str, candidate_ids: Sequence[str], decision: str) -> dict[str, int]:
        status = {"approve": "approved", "reject": "rejected"}.get(decision)
        if not status:
            raise ValueError("Decision must be approve or reject")
        return {"updated": self.store.set_discovery_candidate_status(run_id, candidate_ids, status)}

    def import_to_campaign(
        self, run_id: str, campaign_id: str, candidate_ids: Sequence[str]
    ) -> dict[str, Any]:
        run = self.store.get_discovery_run(run_id)
        if run["campaign_id"] != campaign_id:
            raise ValueError("Discovery run does not belong to this campaign")
        rows = self.store.discovery_candidates_by_id(run_id, candidate_ids)
        added = 0
        existing = 0
        skipped: list[dict[str, str]] = []
        imported_ids: list[str] = []
        for row in rows:
            if row["status"] in {"excluded", "rejected"}:
                skipped.append({"id": row["id"], "reason": row["status"]})
                continue
            contact = ContactInput(
                full_name=row["full_name"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                company=row["company"],
                title=row["title"],
                category=row["category"],
                route=row["route"],
                linkedin_url=row["linkedin_url"],
                public_hook=row["public_hook"],
                hook_source=row["source_url"],
                notes="Discovered from a public page. Review before outreach.",
                source_ref=f"discovery:{run_id}:{row['id']}",
                source_data=row["source_data"],
            )
            contact_id = self.store.upsert_contact(contact)
            _, created = self.store.add_contact_to_campaign(campaign_id, contact_id)
            added += int(created)
            existing += int(not created)
            imported_ids.append(row["id"])
        if imported_ids:
            self.store.set_discovery_candidate_status(run_id, imported_ids, "imported")
            self.store.add_event(
                campaign_id,
                "discovery_contacts_imported",
                {"run_id": run_id, "added": added, "existing": existing},
            )
        return {"added": added, "existing": existing, "skipped": skipped}

    def queue_for_apollo(self, run_id: str, candidate_ids: Sequence[str]) -> dict[str, Any]:
        rows = self.store.discovery_candidates_by_id(run_id, candidate_ids)
        eligible: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        for row in rows:
            if row["status"] in {"excluded", "rejected"}:
                skipped.append({"id": row["id"], "reason": row["status"]})
                continue
            if not row["linkedin_url"] and not (row["full_name"] and row["company"]):
                skipped.append({"id": row["id"], "reason": "missing_name_company_or_linkedin"})
                continue
            eligible.append(row)
        if not eligible:
            return {"queued": 0, "skipped": skipped, "file": ""}

        inbox = self.data_dir / "poi_file_queue" / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        filename = f"discovery_{run_id[:8]}_{uuid.uuid4().hex[:8]}.csv"
        destination = inbox / filename
        fields = [
            "Full Name",
            "First Name",
            "Last Name",
            "Position / Title",
            "Company / Organisation",
            "Company Domain",
            "Category",
            "Country / Region",
            "LinkedIn URL",
            "Email",
            "Source URL",
        ]
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8-sig", newline="", dir=inbox, delete=False, suffix=".tmp"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in eligible:
                writer.writerow(
                    {
                        "Full Name": row["full_name"],
                        "First Name": row["first_name"],
                        "Last Name": row["last_name"],
                        "Position / Title": row["title"],
                        "Company / Organisation": row["company"],
                        "Company Domain": row["company_domain"],
                        "Category": row["category"],
                        "Country / Region": row["country"],
                        "LinkedIn URL": row["linkedin_url"],
                        "Email": row["email"],
                        "Source URL": row["source_url"],
                    }
                )
            temporary = Path(handle.name)
        temporary.replace(destination)
        self.store.set_discovery_candidate_status(
            run_id, [row["id"] for row in eligible], "apollo_queued"
        )
        return {"queued": len(eligible), "skipped": skipped, "file": str(destination)}
