from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from offsetx_apollo_builder.discovery import (
    CrawlPolicy,
    DomainRateLimiter,
    ParsedPage,
    PublicWebCrawler,
)
from offsetx_apollo_builder.outreach.notion import (
    NotionClient,
    NotionError,
    NotionExporter,
    NotionSettingsStore,
    export_sales_leads,
    SALES_LEAD_FIELD_MAP,
)


class _RecordingFetcher:
    """Fake fetcher that records concurrency and serves a tiny link graph."""

    def __init__(self, graph: dict[str, list[str]], tracker: dict[str, Any]) -> None:
        self.graph = graph
        self.tracker = tracker

    def fetch(self, url: str) -> ParsedPage:
        with self.tracker["lock"]:
            self.tracker["active"] += 1
            self.tracker["peak"] = max(self.tracker["peak"], self.tracker["active"])
            self.tracker["urls"].append(url)
        time.sleep(0.02)
        with self.tracker["lock"]:
            self.tracker["active"] -= 1
        return ParsedPage(
            url=url,
            title="t",
            text="",
            links=self.graph.get(url, []),
            people=[],
            content_sha256="x",
        )


def _tracker() -> dict[str, Any]:
    return {"lock": threading.Lock(), "active": 0, "peak": 0, "urls": []}


GRAPH = {
    "https://a.example.com/": ["https://a.example.com/p1", "https://a.example.com/p2"],
    "https://b.example.org/": ["https://b.example.org/p1"],
}


def test_parallel_workers_bounds_are_enforced():
    with pytest.raises(ValueError):
        CrawlPolicy(allowed_domains=("example.com",), parallel_workers=0)
    with pytest.raises(ValueError):
        CrawlPolicy(allowed_domains=("example.com",), parallel_workers=5)


def test_parallel_crawl_visits_same_pages_as_sequential():
    policy_kwargs = dict(
        allowed_domains=("a.example.com", "b.example.org"),
        max_pages=10,
        max_depth=1,
        request_delay_seconds=0.5,
    )
    seq_tracker = _tracker()
    sequential = PublicWebCrawler(
        CrawlPolicy(**policy_kwargs, parallel_workers=1),
        _RecordingFetcher(GRAPH, seq_tracker),
    ).crawl(list(GRAPH))

    par_tracker = _tracker()
    parallel = PublicWebCrawler(
        CrawlPolicy(**policy_kwargs, parallel_workers=3),
        _RecordingFetcher(GRAPH, par_tracker),
        fetcher_factory=lambda: _RecordingFetcher(GRAPH, par_tracker),
    ).crawl(list(GRAPH))

    assert {page.url for page in sequential.pages} == {page.url for page in parallel.pages}
    assert not parallel.errors
    assert par_tracker["peak"] >= 2  # actually ran concurrently


def test_parallel_crawl_respects_max_pages():
    tracker = _tracker()
    result = PublicWebCrawler(
        CrawlPolicy(
            allowed_domains=("a.example.com", "b.example.org"),
            max_pages=2,
            max_depth=1,
            request_delay_seconds=0.5,
            parallel_workers=3,
        ),
        _RecordingFetcher(GRAPH, tracker),
        fetcher_factory=lambda: _RecordingFetcher(GRAPH, tracker),
    ).crawl(list(GRAPH))
    assert len(result.pages) == 2


def test_domain_rate_limiter_serializes_same_domain():
    limiter = DomainRateLimiter(0.08)
    stamps: list[float] = []

    def hit() -> None:
        limiter.wait_turn("https://a.example.com/x")
        stamps.append(time.monotonic())

    threads = [threading.Thread(target=hit) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    stamps.sort()
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert all(gap >= 0.06 for gap in gaps), gaps


# ---------------------------------------------------------------------------
# Notion


def test_notion_settings_store_encrypts_token(tmp_path):
    store = NotionSettingsStore(tmp_path)
    assert store.status()["connected"] is False
    store.update(token="secret_abc123", workspace_name="OffsetX HQ")
    assert store.token() == "secret_abc123"
    assert store.status()["connected"] is True
    raw = (tmp_path / "notion_secret.bin").read_bytes()
    assert b"secret_abc123" not in raw  # never plaintext on disk
    settings_raw = (tmp_path / "notion_settings.json").read_text()
    assert "secret_abc123" not in settings_raw
    store.disconnect()
    assert store.status()["connected"] is False


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
        self.reason = "reason"

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSession:
    """Simulates a Notion database with a title + a few properties."""

    def __init__(self) -> None:
        self.pages: dict[str, dict[str, Any]] = {}
        self.schema = {
            "Name": {"type": "title"},
            "Company": {"type": "rich_text"},
            "Stage": {"type": "select"},
            "Deal value": {"type": "number"},
        }
        self.calls: list[str] = []

    def request(self, method: str, url: str, headers=None, json=None, timeout=0):
        self.calls.append(f"{method} {url}")
        if url.endswith("/users/me"):
            return _FakeResponse(200, {"name": "off_CRM bot"})
        if "/databases/db1/query" in url:
            wanted = json["filter"]["title"]["equals"] if "title" in json["filter"] else ""
            for page_id, props in self.pages.items():
                if props.get("_title") == wanted:
                    return _FakeResponse(200, {"results": [{"id": page_id}]})
            return _FakeResponse(200, {"results": []})
        if url.endswith("/databases/db1"):
            return _FakeResponse(200, {"properties": self.schema})
        if url.endswith("/pages") and method == "POST":
            page_id = f"page-{len(self.pages) + 1}"
            title = json["properties"]["Name"]["title"][0]["text"]["content"]
            self.pages[page_id] = {"_title": title, **json["properties"]}
            return _FakeResponse(200, {"id": page_id})
        if "/pages/" in url and method == "PATCH":
            page_id = url.rsplit("/", 1)[1]
            self.pages[page_id].update(json["properties"])
            return _FakeResponse(200, {"id": page_id})
        return _FakeResponse(404, {"message": "not found"})


def test_notion_export_upserts_and_reports_skipped_fields():
    session = _FakeSession()
    exporter = NotionExporter(NotionClient("token", session=session))

    def list_leads(**_kwargs):
        return (
            [
                {
                    "lead_name": "Asha Rao",
                    "company": "GreenSteel",
                    "status": "proposal",
                    "total_deal_value": "5000",
                    "email": "asha@greensteel.example",
                },
                {"lead_name": "Vikram J", "company": "CarbonCo", "status": "new"},
            ],
            2,
        )

    first = export_sales_leads(exporter=exporter, database_id="db1", list_leads=list_leads)
    assert first["created"] == 2 and first["updated"] == 0 and first["failed"] == 0
    # Email/Setter/Source/etc. do not exist in this database schema -> reported, not errored.
    assert "Email" in first["skipped_fields"]

    second = export_sales_leads(exporter=exporter, database_id="db1", list_leads=list_leads)
    assert second["created"] == 0 and second["updated"] == 2  # idempotent upsert


def test_notion_client_maps_auth_errors_to_clear_message():
    class _Denied:
        def request(self, *args, **kwargs):
            return _FakeResponse(401, {"message": "unauthorized"})

    client = NotionClient("bad", session=_Denied())
    with pytest.raises(NotionError, match="token"):
        client.me()


def test_notion_client_requires_token():
    with pytest.raises(NotionError, match="not connected"):
        NotionClient("")
