from __future__ import annotations

import sys
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.discovery import (
    Crawl4AIPageFetcher,
    CrawlPolicy,
    DiscoveredPerson,
    DiscoveryService,
    ParsedPage,
    ScraplingPageParser,
    SafePublicFetcher,
    DiscoveryFetchError,
    _PinnedPublicAdapter,
    validate_public_url,
)
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.research import compile_discovery_plan
from offsetx_apollo_builder.io_utils import (
    append_apollo_rejection_ledger,
    append_exclusion_ledger,
)


HTML = b"""
<html><head><title>Example leadership</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Person",
      "name": "Anita Rao",
      "jobTitle": "Climate Lead",
      "worksFor": {"@type": "Organization", "name": "Example Exports", "url": "https://example.com"},
      "sameAs": ["https://www.linkedin.com/in/anita-rao"],
      "description": "Leads public CBAM readiness work."
    }
  ]
}
</script></head><body><a href="/about">About</a></body></html>
"""


class StaticFetcher:
    def __init__(self, people: list[DiscoveredPerson]):
        self.people = people

    def fetch(self, url: str) -> ParsedPage:
        return ParsedPage(
            url=url,
            title="Public team page",
            text="Public team information",
            links=[],
            people=self.people,
            content_sha256="a" * 64,
        )


def test_public_url_policy_blocks_social_and_private_targets():
    assert validate_public_url(
        "https://www.example.com/team#people", allowed_domains=["example.com"]
    ) == "https://www.example.com/team"
    with pytest.raises(ValueError, match="official API"):
        validate_public_url("https://linkedin.com/in/person", allowed_domains=["linkedin.com"])
    with pytest.raises(ValueError, match="reserved network"):
        validate_public_url("http://127.0.0.1/admin")
    with pytest.raises(ValueError, match="credentials"):
        validate_public_url("https://user:secret@example.com/team")
    with pytest.raises(ValueError, match="outside"):
        validate_public_url("https://other.test/team", allowed_domains=["example.com"])


def test_A08_public_fetch_connects_to_the_verified_address_not_second_dns(monkeypatch):
    """A real HTTP request through the public fetcher, with DNS changing.

    The intended address is public. A socket that resolved the hostname again
    could reach a rebinding private address. The fixture routes the *verified*
    numeric destination to an isolated local test server, retaining the Host.
    """
    from urllib3.util import connection as transport

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.server.recorded_host = self.headers["Host"]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html>public</html>")

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    attempts = []
    actual_connect = transport.create_connection

    def connect(address, *args, **kwargs):
        attempts.append(address)
        # A checked public IP is deliberately mapped to the controlled local
        # fixture. Connecting by hostname instead would fail this assertion.
        assert address[0] == "93.184.216.34", "unverified DNS lookup at connect"
        return actual_connect(("127.0.0.1", server.server_port), *args, **kwargs)

    def resolver(host, port, **kwargs):
        assert host == "outside.example"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    try:
        monkeypatch.setattr(transport, "create_connection", connect)
        guard = SafePublicFetcher(
            CrawlPolicy(allowed_domains=("outside.example",), request_delay_seconds=0),
            resolver=resolver,
        )
        body, final_url, code = guard._request_bytes(
            "http://outside.example/info", max_bytes=1_000, accepted_types=("text/html",)
        )
        assert (body, code) == (b"<html>public</html>", 200)
        assert final_url == "http://outside.example/info"
        assert attempts == [("93.184.216.34", 80)]
        assert server.recorded_host == "outside.example"
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_A08_rejects_private_dns_before_any_http_socket(monkeypatch):
    from urllib3.util import connection as transport

    attempts = []

    def socket_attempt(*args, **kwargs):
        attempts.append((args, kwargs))
        raise AssertionError("a private destination must not be contacted")

    guard = SafePublicFetcher(
        CrawlPolicy(allowed_domains=("outside.example",), request_delay_seconds=0),
        resolver=lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", port))
        ],
    )
    monkeypatch.setattr(transport, "create_connection", socket_attempt)
    with pytest.raises(DiscoveryFetchError, match="Private, local and reserved"):
        guard._request_bytes("http://outside.example/", max_bytes=300,
                             accepted_types=("text/html",))
    assert not attempts


def test_A08_tls_hostname_is_preserved_when_connecting_to_pinned_ip():
    adapter = _PinnedPublicAdapter("93.184.216.34")
    try:
        pool = adapter.poolmanager.connection_from_url("https://outside.example/team")
        conn = pool.ConnectionCls(host=pool.host, port=pool.port)
        assert conn.host == "outside.example"  # SNI/certificate hostname
        assert conn._dns_host == "93.184.216.34"  # TCP address
    finally:
        adapter.close()


def test_A08_custom_proxy_is_refused_even_if_dns_target_is_public():
    session = requests.Session()
    session.proxies["http"] = "http://127.0.0.1:8080"
    fetcher = SafePublicFetcher(
        CrawlPolicy(allowed_domains=("outside.example",), request_delay_seconds=0),
        session=session,
        resolver=lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))
        ],
    )
    with pytest.raises(DiscoveryFetchError, match="proxies or custom transports"):
        fetcher._request_bytes(
            "http://outside.example/", max_bytes=400, accepted_types=("text/html",)
        )


def test_scrapling_parser_extracts_structured_people_without_fetcher_stealth():
    page = ScraplingPageParser().parse(HTML, "https://example.com/team")
    assert page.title == "Example leadership"
    assert page.links == ["https://example.com/about"]
    assert len(page.people) == 1
    person = page.people[0]
    assert person.full_name == "Anita Rao"
    assert person.company == "Example Exports"
    assert person.company_domain == "example.com"
    assert person.linkedin_url == "https://www.linkedin.com/in/anita-rao"
    assert person.social_handles == {
        "linkedin": ["https://www.linkedin.com/in/anita-rao"]
    }
    assert person.public_hook == "Leads public CBAM readiness work."


def test_prompt_compiler_creates_bounded_inspectable_plan():
    plan = compile_discovery_plan(
        "Find 100 competitors, their sales employees and social handles; check who interacted."
    )
    assert plan.target_count == 100
    assert plan.company_mode == "competitor_expansion"
    assert "sales" in plan.role_groups
    assert plan.collect_social_handles is True
    assert plan.collect_interactions is True
    assert "search_api" in plan.source_adapters
    assert len(plan.blocked_requirements) == 2


def test_crawl4ai_adapter_hard_disables_evasive_browser_features(monkeypatch):
    captured: dict[str, dict] = {}

    class Config:
        def __init__(self, **kwargs):
            captured[self.__class__.__name__] = kwargs

    class BrowserConfig(Config):
        pass

    class CrawlerRunConfig(Config):
        pass

    class FakeStrategy:
        def set_hook(self, *_):
            pass

    class FakeCrawler:
        def __init__(self, config):
            self.config = config
            self.crawler_strategy = FakeStrategy()

    monkeypatch.setitem(
        sys.modules,
        "crawl4ai",
        SimpleNamespace(
            AsyncWebCrawler=FakeCrawler,
            BrowserConfig=BrowserConfig,
            CrawlerRunConfig=CrawlerRunConfig,
            CacheMode=SimpleNamespace(BYPASS="bypass"),
        ),
    )
    fetcher = Crawl4AIPageFetcher(
        CrawlPolicy(allowed_domains=("example.com",)),
        parser=SimpleNamespace(parse=lambda *_: None),
    )
    try:
        assert captured["BrowserConfig"]["enable_stealth"] is False
        assert captured["BrowserConfig"]["use_persistent_context"] is False
        assert captured["BrowserConfig"]["cookies"] == []
        assert captured["CrawlerRunConfig"]["simulate_user"] is False
        assert captured["CrawlerRunConfig"]["override_navigator"] is False
        assert captured["CrawlerRunConfig"]["magic"] is False
        assert captured["CrawlerRunConfig"]["max_retries"] == 0
        assert captured["CrawlerRunConfig"]["check_robots_txt"] is True
    finally:
        fetcher.close()


def test_discovery_dedupes_old_pois_then_queues_and_imports_reviewed_people(tmp_path):
    project_root = tmp_path / "project"
    old_pois = project_root / "old_pois"
    old_pois.mkdir(parents=True)
    (old_pois / "known.csv").write_text(
        "Full Name,Company / Organisation,Email\nKnown Person,Known Co,known@example.com\n",
        encoding="utf-8",
    )
    store = OutreachStore(tmp_path / "crm.db")
    store.initialize()
    campaign_id = store.create_campaign(name="Discovery pilot", daily_send_limit=10)
    people = [
        DiscoveredPerson(
            full_name="Known Person",
            email="known@example.com",
            company="Known Co",
            title="Director",
        ),
        DiscoveredPerson(
            full_name="Fresh Person",
            first_name="Fresh",
            last_name="Person",
            company="Fresh Co",
            company_domain="fresh.example",
            title="Carbon Manager",
            public_hook="Runs the public carbon programme.",
            confidence=0.91,
            social_handles={"linkedin": ["https://www.linkedin.com/in/fresh-person"]},
        ),
    ]
    service = DiscoveryService(
        store,
        project_root=project_root,
        data_dir=tmp_path / "data",
        fetcher_factory=lambda _: StaticFetcher(people),
    )
    run = service.run(
        campaign_id=campaign_id,
        seed_urls=["https://example.com/team"],
        max_pages=5,
        max_depth=0,
    )
    assert run["pages_crawled"] == 1
    assert run["fresh_count"] == 1
    assert run["excluded_count"] == 1

    candidates, total = store.list_discovery_candidates(run["id"])
    assert total == 2
    fresh = next(item for item in candidates if item["full_name"] == "Fresh Person")
    known = next(item for item in candidates if item["full_name"] == "Known Person")
    assert fresh["status"] == "new"
    assert known["status"] == "excluded"
    assert known["exclusion_reason"] == "duplicate_email"

    graph = service.research_graph(run_id=run["id"])
    assert graph["stats"]["by_type"]["person"] == 2
    assert graph["stats"]["by_type"]["company"] == 2
    assert graph["stats"]["by_type"]["social_profile"] == 1
    assert graph["stats"]["by_relation"]["WORKS_AT"] == 2
    assert all("email" not in node["properties"] for node in graph["nodes"])

    queued = service.queue_for_apollo(run["id"], [fresh["id"], known["id"]])
    assert queued["queued"] == 1
    queue_file = Path(queued["file"])
    assert queue_file.exists()
    assert "Fresh Person" in queue_file.read_text(encoding="utf-8-sig")

    imported = service.import_to_campaign(run["id"], campaign_id, [fresh["id"], known["id"]])
    assert imported["added"] == 1
    contacts, contact_total = store.list_campaign_contacts(campaign_id)
    assert contact_total == 1
    assert contacts[0]["full_name"] == "Fresh Person"
    store.close()


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )


def test_discovery_api_requires_robots_and_uses_injected_public_fetcher(tmp_path):
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        app.state.discovery_fetcher_factory = lambda _: StaticFetcher(
            [
                DiscoveredPerson(
                    full_name="Public Lead",
                    company="Example Co",
                    title="Sustainability Manager",
                )
            ]
        )
        campaign_id = client.post("/api/v1/campaigns", json={"name": "API crawl"}).json()["id"]
        unsafe_policy = client.post(
            f"/api/v1/campaigns/{campaign_id}/discovery/runs",
            json={"seed_urls": ["https://example.com/team"], "obey_robots": False},
        )
        assert unsafe_policy.status_code == 422
        created = client.post(
            f"/api/v1/campaigns/{campaign_id}/discovery/runs",
            json={"seed_urls": ["https://example.com/team"], "max_depth": 0},
        )
        assert created.status_code == 201
        assert created.json()["fresh_count"] == 1
        assert created.json()["plan"]["target_count"] == 100
        run_id = created.json()["id"]
        listed = client.get(f"/api/v1/discovery/runs/{run_id}/candidates")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["full_name"] == "Public Lead"
        graph = client.get(f"/api/v1/research/graph?run_id={run_id}")
        assert graph.status_code == 200
        assert graph.json()["stats"]["nodes"] >= 3
        interaction = client.post(
            "/api/v1/research/interactions",
            json={
                "actor_name": "Public Lead",
                "actor_handle": "https://www.linkedin.com/in/public-lead",
                "target_name": "Example Co",
                "target_handle": "https://www.linkedin.com/company/example-co",
                "platform": "linkedin",
                "interaction_type": "comment",
                "source_url": "https://www.linkedin.com/posts/public-evidence",
                "source_type": "manual_import",
                "rights_basis": "public_evidence",
            },
        )
        assert interaction.status_code == 201
        full_graph = client.get("/api/v1/research/graph?limit=300").json()
        assert full_graph["stats"]["by_relation"]["INTERACTED_WITH"] == 1

        output_root = tmp_path / "output_apollo"
        output_run = output_root / "runs" / "api-run"
        output_run.mkdir(parents=True)
        append_apollo_rejection_ledger(
            output_root,
            [
                {
                    "Decision": "rejected_after_enrichment",
                    "Reason": "enriched_no_email",
                    "Full Name": "No Email Lead",
                    "Company / Organisation": "Example Co",
                }
            ],
            output_run,
            "api-run",
        )
        rejected = client.get("/api/v1/apollo/rejections")
        assert rejected.status_code == 200
        assert rejected.json()["items"][0]["reason"] == "enriched_no_email"
        accepted_dir = tmp_path / "old_pois"
        append_exclusion_ledger(
            accepted_dir,
            [
                {
                    "Apollo Person ID": "b" * 24,
                    "Email": "accepted@example.com",
                    "Full Name": "Accepted Lead",
                    "Company / Organisation": "Example Co",
                }
            ],
            output_run,
        )
        accepted = client.get("/api/v1/apollo/exclusions")
        assert accepted.status_code == 200
        assert accepted.json()["items"][0]["email"] == "accepted@example.com"
