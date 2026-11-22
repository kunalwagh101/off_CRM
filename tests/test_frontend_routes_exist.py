"""Every API path a screen calls is a route the server has.

Audit finding A35: the Connectors screen asked for `/api/v1/status`, a route that
never existed, so its Gmail panel showed an error to every owner who opened it.
Nothing failed, because the frontend tests render screens without a server and
the backend tests never read the frontend. This reads both.

Literal API calls and local helper-generated paths are checked. Unknown helpers
fail closed rather than silently vanishing from the inventory. `${…}` segments
match server path parameters, and query strings are ignored.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import API_PREFIX, create_app
from offsetx_apollo_builder.api.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"

METHODS = {
    "get": "GET",
    "download": "GET",
    "url": "GET",
    "post": "POST",
    "upload": "POST",
    "postDownload": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
}
CALL = re.compile(
    r"api\.(?P<method>" + "|".join(METHODS) + r")(?:<[^()]*>)?\s*\(\s*(?P<quote>[`\"'])(?P<path>/[^`\"']*)(?P=quote)"
)


HELPER_CALL = re.compile(
    r"api\.(?P<method>" + "|".join(METHODS)
    + r")(?:<[^()]*>)?\s*\(\s*(?P<helper>[A-Za-z_$][\w$]*)\s*\("
)


def _indirect_path(source: str, helper: str) -> str:
    """Resolve a simple local helper, refusing unknown dynamic route logic."""
    signature = re.search(
        rf"\b(?:export\s+)?function\s+{re.escape(helper)}\s*\([^)]*\)\s*:\s*string\s*\{{",
        source,
    )
    if signature is None:
        raise AssertionError(f"A35 unresolved indirect API route helper: {helper}")
    end = re.search(r"(?m)^\s*}\s*$", source[signature.end():])
    body = source[signature.end():signature.end() + end.start()] if end else ""
    route = re.search(
        r"\breturn\s+(?:pagePath\(\s*)?(?P<quote>[\x60\"'])(?P<path>/[^\x60\"']*)(?P=quote)",
        body,
    )
    if route is None:
        raise AssertionError(f"A35 unresolved indirect API route helper: {helper}")
    return route.group("path").split("?", 1)[0]


def _called() -> set[tuple[str, str, str]]:
    calls = set()
    for path in FRONTEND.rglob("*.ts*"):
        if ".test." in path.name:
            continue
        source = path.read_text(encoding="utf-8")
        for match in CALL.finditer(source):
            target = match.group("path").split("?", 1)[0]
            calls.add((METHODS[match.group("method")], target, path.name))
        for match in HELPER_CALL.finditer(source):
            target = _indirect_path(source, match.group("helper"))
            calls.add((METHODS[match.group("method")], target, path.name))
    return calls


def _segments(path: str, wildcard: str) -> list[str]:
    return [wildcard if re.search(r"\$\{|^\{.*\}$", part) else part for part in path.strip("/").split("/")]


def _routes(app) -> set[tuple[str, tuple[str, ...]]]:
    def flatten(routes):
        for route in routes:
            nested = getattr(route, "original_router", None)
            yield from flatten(nested.routes) if nested is not None else [route]

    found = set()
    for route in flatten(app.routes):
        if isinstance(route, APIRoute) and route.path.startswith(API_PREFIX + "/"):
            relative = route.path[len(API_PREFIX):]
            for method in route.methods or ():
                found.add((method, tuple(_segments(relative, "*"))))
    return found


def _matches(method: str, call: list[str], routes) -> bool:
    for route_method, route in routes:
        if route_method != method or len(route) != len(call):
            continue
        if all(r == "*" or c == "*" or r == c for r, c in zip(route, call)):
            return True
    return False


def test_every_api_path_a_screen_calls_exists(tmp_path):
    settings = AppSettings(
        project_root=ROOT,
        database_path=tmp_path / "data" / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "data" / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )
    with TestClient(create_app(settings)) as client:
        routes = _routes(client.app)
    calls = _called()
    assert len(calls) > 50, "the call pattern stopped matching the frontend"
    missing = sorted(
        f"{method} {path}  ({source})"
        for method, path, source in calls
        if not _matches(method, _segments(path, "*"), routes)
    )
    assert missing == []


def test_A35_literal_route_scan_covers_nested_generic_type_arguments():
    """Do not skip calls using common nested TypeScript response wrappers."""
    sample = """
        api.get<Paginated<Contact>>("/contacts")
        api.post<Promise<Result<Item>>>(
            "/campaigns"
        )
        api.get("/meta")
    """
    found = {
        (match.group("method"), match.group("path"))
        for match in CALL.finditer(sample)
    }
    assert found == {
        ("get", "/contacts"),
        ("post", "/campaigns"),
        ("get", "/meta"),
    }


def test_A35_indirect_helpers_include_template_and_paginated_routes(tmp_path, monkeypatch):
    """An API call via a page helper must be checked against server routes."""
    frontend = tmp_path / "src"
    frontend.mkdir()
    (frontend / "Helpers.tsx").write_text(
        """
        export function queuePagePath(id: string): string {
          return `/campaigns/${encodeURIComponent(id)}/queue?limit=100`;
        }
        api.get<QueueResponse>(queuePagePath(campaignId));
        export function qualityPath(page: number): string {
          return pagePath("/crm/quality", {}, page);
        }
        api.get(qualityPath(page));
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "FRONTEND", frontend)
    assert _called() == {
        ("GET", "/campaigns/${encodeURIComponent(id)}/queue", "Helpers.tsx"),
        ("GET", "/crm/quality", "Helpers.tsx"),
    }


def test_A35_unknown_indirect_helpers_fail_closed(tmp_path, monkeypatch):
    """Never quietly ignore an indirect API path that cannot be resolved."""
    frontend = tmp_path / "src"
    frontend.mkdir()
    (frontend / "Unknown.tsx").write_text(
        "api.get<Payload>(missingRoute(value))",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "FRONTEND", frontend)
    with pytest.raises(AssertionError, match="A35 unresolved indirect API route helper"):
        _called()
