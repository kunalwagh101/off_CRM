"""Every API path a screen calls is a route the server has.

Audit finding A35: the Connectors screen asked for `/api/v1/status`, a route that
never existed, so its Gmail panel showed an error to every owner who opened it.
Nothing failed, because the frontend tests render screens without a server and
the backend tests never read the frontend. This reads both.

Only paths written out at the call site are checked — a path assembled in a
variable first is invisible here. `${…}` parts match one path segment, the way
a `{param}` does on the server; a query string is ignored.
"""
from __future__ import annotations

import re
from pathlib import Path

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
    r"api\.(?P<method>" + "|".join(METHODS) + r")(?:<[^>(]*>)?\(\s*(?P<quote>[`\"'])(?P<path>/[^`\"']*)(?P=quote)"
)


def _called() -> set[tuple[str, str, str]]:
    calls = set()
    for path in FRONTEND.rglob("*.ts*"):
        if ".test." in path.name:
            continue
        for match in CALL.finditer(path.read_text(encoding="utf-8")):
            target = match.group("path").split("?", 1)[0]
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
