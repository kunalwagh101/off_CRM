#!/usr/bin/env python3
"""One-shot, assertion-backed delivery helper for S-06.02.02.

Edits are anchored and fail closed: if the repository has drifted, this script
stops rather than guessing. The temporary workflow is created/removed through
the GitHub connector, following the repository's existing one-shot pattern.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def write(name: str, text: str) -> None:
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def pull() -> None:
    backlog = read("PRODUCT_BACKLOG.md")
    old_story = """#### S-06.02.02 — Every endpoint authorises and validates
- **Given** any endpoint, **when** called without a session, **then** it refuses.
- **Given** any body, **when** it is malformed, **then** the response is a 4xx
  with a message and never a stack trace.
- **Dependencies:** none. **Size:** M. **Indicator:** unauthenticated reachability.
"""
    new_story = """#### S-06.02.02 — Every endpoint authorises and validates

**User story.** As the CRM owner, I want every API boundary to authenticate,
authorise and validate before business logic runs, so that malformed or
unauthorised requests cannot read, mutate or trigger CRM state.

- **Given** any protected API route and HTTP method, **when** it is called
  without a valid owner credential, **then** it returns `401` before the route
  handler executes.
- **Given** a new protected route under `/api/`, **when** it is added without a
  special exemption, **then** the central policy protects it by default; public
  exemptions are explicit and method-specific.
- **Given** any protected endpoint with a request body, **when** malformed input
  is sent with a valid credential, **then** FastAPI/Pydantic rejects it with a
  4xx before the route handler executes.
- **Given** caller-supplied identity/workspace-like headers or a wrong token,
  **when** no valid owner credential is present, **then** they grant no
  authority and the request is refused.
- **Given** an intentionally public boundary (metadata, login/session/logout,
  signed unsubscribe, or SES/SNS webhook), **when** it is called, **then** only
  its declared HTTP method is public and its own token/signature/input control
  still rejects invalid input.
- **Given** an unauthorised or malformed request, **when** it is rejected,
  **then** the response is a 4xx with a useful message and contains no Python
  traceback or internal stack path.

**Dependencies:** none. **Blocking risk:** object-level workspace/resource
ownership does not exist in the current single-owner product; `S-06.01.01`
owns multi-workspace login and isolation and remains a separate vertical slice.
**Size:** M. **Indicator:** unauthenticated reachability and pre-handler rejection
coverage. **Business value:** `E-06` — the product can be run safely in
production without an API boundary becoming the easiest path around its controls.

##### T-06.02.02.a — Inventory and classify every current API route
Enumerate registered `/api/` route+method pairs and make public exceptions explicit.

##### T-06.02.02.b — Make public exemptions fail closed
Reuse the central middleware; narrow exemptions by HTTP method instead of adding
per-route auth wrappers.

##### T-06.02.02.c — Prove validation happens before business logic
Exercise every protected body-bearing route with malformed authenticated input.

##### T-06.02.02.d — Add negative/security regression coverage
Cover anonymous, wrong-token, spoofed-identity, malformed-body, public-boundary
and no-stack-trace paths.

##### T-06.02.02.e — Close documentation and evidence
Update security docs, traceability, demo, changelog, defect/decision logs, board
evidence and retrospective.

### OUT_OF_SCOPE — S-06.02.02

- Multi-user/workspace ownership and cross-workspace object authorisation:
  `S-06.01.01` defines those identities and storage boundaries; inventing them
  here would silently absorb another READY story.
- Role/permission tiers: `S-06.01.02` owns that business rule.
- New OAuth/provider authentication schemes: existing owner token/session
  mechanisms are hardened rather than replaced.
"""
    backlog = replace_once(backlog, old_story, new_story, label="refine S-06.02.02")
    backlog = replace_once(
        backlog,
        "| R-48 | Every endpoint authorises and validates its input | S-06.02.02 |",
        "| R-48 | Every API route is explicitly public or owner-protected; protected calls reject anonymous/spoofed callers, input is validated before business logic, public callbacks self-authorise, and 4xx errors expose no stack trace | S-06.02.02 |",
        label="expand R-48 coverage",
    )
    write("PRODUCT_BACKLOG.md", backlog)

    board = read("BOARD.md")
    story = "- S-06.02.02 · Every endpoint authorises and validates\n"
    board = replace_once(board, story, "", label="remove S-06.02.02 from READY")
    board = replace_once(
        board,
        "## IN_PROGRESS\n\n_nothing in flight_\n",
        "## IN_PROGRESS\n\n- S-06.02.02 · Every endpoint authorises and validates\n",
        label="pull S-06.02.02",
    )
    write("BOARD.md", board)

    trace = read("TRACEABILITY.md")
    trace = replace_once(
        trace,
        "| R-48 | S-06.02.02 | 2 | — | — |",
        "| R-48 | S-06.02.02 | 6 | — | — |",
        label="refined trace criteria count",
    )
    write("TRACEABILITY.md", trace)

    defects = read("DEFECT_LOG.md")
    d50 = "| D-50 | 2026-09-17 | process | low | The S-06.02.17 one-shot delivery helper contained an uncompiled nested string and failed before pulling the story | fixed during `S-06.02.17` — one-shot helpers are syntax-compiled before execution |\n"
    d51 = d50 + "| D-51 | 2026-09-18 | process | medium | TRACEABILITY.md hand-maintained status prose said 0 READY / 1 IN_REVIEW while BOARD.md had READY work and nothing in review | fixed · `S-06.02.02` removes hand-maintained status counts |\n"
    defects = replace_once(defects, d50, d51, label="log D-51")
    write("DEFECT_LOG.md", defects)


def implement() -> None:
    app = read("offsetx_apollo_builder/api/app.py")

    constants = """API_PREFIX = "/api/v1"
LIVE_SEND_CONFIRMATION = "SEND LIVE EMAILS"
CONTACT_UPLOAD_TYPES = {".csv", ".xlsx", ".xls"}
EXPERT_UPLOAD_TYPES = {".md", ".txt"}
"""
    public_policy = constants + """

# Authentication is fail-closed for `/api/`. These are the only route+method
# pairs that are intentionally reachable without the owner credential. Keep the
# method in the key: a path-wide exemption makes any future sensitive method on
# the same URL public by accident.
PUBLIC_API_EXACT = frozenset(
    {
        ("GET", f"{API_PREFIX}/meta"),
        ("GET", f"{API_PREFIX}/auth/session"),
        ("POST", f"{API_PREFIX}/auth/login"),
        ("POST", f"{API_PREFIX}/auth/logout"),
        ("POST", f"{API_PREFIX}/email-delivery/events/ses/sns"),
    }
)
PUBLIC_API_PREFIX_METHODS = (
    ("GET", f"{API_PREFIX}/email/unsubscribe/"),
    ("POST", f"{API_PREFIX}/email/unsubscribe/"),
)


def _is_public_api_request(method: str, path: str) -> bool:
    verb = method.upper()
    if (verb, path) in PUBLIC_API_EXACT:
        return True
    return any(
        verb == allowed_method and path.startswith(prefix)
        for allowed_method, prefix in PUBLIC_API_PREFIX_METHODS
    )
"""
    app = replace_once(app, constants, public_policy, label="method-specific public API policy")

    old_public = """        public_paths = {
            f"{API_PREFIX}/meta",
            f"{API_PREFIX}/auth/session",
            f"{API_PREFIX}/auth/login",
            f"{API_PREFIX}/auth/logout",
        }
        public_prefixes = (
            f"{API_PREFIX}/email/unsubscribe/",
            f"{API_PREFIX}/email-delivery/events/ses/sns",
        )
        is_public = request.url.path in public_paths or request.url.path.startswith(
            public_prefixes
        )
"""
    new_public = """        is_public = _is_public_api_request(request.method, request.url.path)
"""
    app = replace_once(app, old_public, new_public, label="central middleware public classification")

    app = replace_once(
        app,
        '"authenticated": not session_auth.enabled or bool(identity) or token_authenticated,',
        '"authenticated": bool(identity) or token_authenticated,',
        label="truthful auth session state",
    )
    write("offsetx_apollo_builder/api/app.py", app)

    test_file = r'''from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


API_PREFIX = "/api/v1"
PUBLIC_EXACT = {
    ("GET", f"{API_PREFIX}/meta"),
    ("GET", f"{API_PREFIX}/auth/session"),
    ("POST", f"{API_PREFIX}/auth/login"),
    ("POST", f"{API_PREFIX}/auth/logout"),
    ("POST", f"{API_PREFIX}/email-delivery/events/ses/sns"),
}
PUBLIC_PREFIX_METHODS = (
    ("GET", f"{API_PREFIX}/email/unsubscribe/"),
    ("POST", f"{API_PREFIX}/email/unsubscribe/"),
)
STACK_MARKERS = ("traceback (most recent call last)", "site-packages/", 'file "')


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=tmp_path,
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        api_token="k" * 40,
        allowed_hosts=("testserver",),
    )


def _api_routes(app) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/")
    ]


def _is_public(method: str, path: str) -> bool:
    verb = method.upper()
    if (verb, path) in PUBLIC_EXACT:
        return True
    return any(
        verb == allowed and path.startswith(prefix)
        for allowed, prefix in PUBLIC_PREFIX_METHODS
    )


def _concrete_path(route: APIRoute) -> str:
    values: dict[str, str] = {}
    for name, convertor in route.param_convertors.items():
        kind = type(convertor).__name__.lower()
        if "int" in kind:
            values[name] = "1"
        elif "float" in kind:
            values[name] = "1.0"
        elif "uuid" in kind:
            values[name] = "00000000-0000-4000-8000-000000000001"
        elif name == "email":
            values[name] = "boundary@example.com"
        else:
            values[name] = "boundary-probe"
    path = route.path
    for name, value in values.items():
        path = re.sub(r"\{" + re.escape(name) + r"(?::[^}]+)?\}", value, path)
    return path


def _methods(route: APIRoute) -> list[str]:
    return sorted((route.methods or set()) - {"HEAD", "OPTIONS"})


def _assert_safe_4xx(response) -> None:
    assert 400 <= response.status_code < 500, response.text
    lowered = response.text.lower()
    for marker in STACK_MARKERS:
        assert marker not in lowered, response.text


def test_every_current_protected_api_route_rejects_anonymous_requests(tmp_path):
    app = create_app(_settings(tmp_path))
    checked: list[str] = []
    with TestClient(app, raise_server_exceptions=False) as client:
        for route in _api_routes(app):
            for method in _methods(route):
                if _is_public(method, route.path):
                    continue
                response = client.request(method, _concrete_path(route))
                assert response.status_code == 401, (
                    f"{method} {route.path} was reachable without owner auth: "
                    f"{response.status_code} {response.text}"
                )
                assert response.json() == {"detail": "CRM login required"}
                checked.append(f"{method} {route.path}")
    assert checked, "route inventory unexpectedly contained no protected API routes"


def test_a_future_method_under_a_public_prefix_is_protected_by_default(tmp_path):
    app = create_app(_settings(tmp_path))

    @app.delete(f"{API_PREFIX}/email/unsubscribe/admin-probe")
    def privileged_probe():
        return {"should_not_be_public": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.delete(f"{API_PREFIX}/email/unsubscribe/admin-probe")
    assert response.status_code == 401
    assert response.json() == {"detail": "CRM login required"}


def test_auth_session_never_claims_anonymous_api_token_user_is_authenticated(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        anonymous = client.get(f"{API_PREFIX}/auth/session")
        assert anonymous.status_code == 200
        assert anonymous.json()["authenticated"] is False
        authorised = client.get(
            f"{API_PREFIX}/auth/session",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
        assert authorised.status_code == 200
        assert authorised.json()["authenticated"] is True


def test_spoofed_identity_headers_and_wrong_token_have_no_authority(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        spoofed = client.get(
            f"{API_PREFIX}/dashboard",
            headers={
                "X-User": "owner",
                "X-Workspace": "workspace-1",
                "X-Offsetx-Token": "not-the-real-token",
            },
        )
        assert spoofed.status_code == 401
        _assert_safe_4xx(spoofed)

        authorised = client.get(
            f"{API_PREFIX}/dashboard",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
        assert authorised.status_code == 200


def test_every_protected_body_route_rejects_malformed_input_before_handler(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)
    headers = {
        "Authorization": f"Bearer {settings.api_token}",
        "Content-Type": "application/json",
    }
    checked: list[str] = []

    with TestClient(app, raise_server_exceptions=False) as client:
        for route in _api_routes(app):
            if route.body_field is None:
                continue
            for method in _methods(route):
                if _is_public(method, route.path):
                    continue
                called: list[str] = []
                original = route.dependant.call

                def must_not_run(*args, **kwargs):
                    called.append(route.path)
                    raise AssertionError("business logic ran before request validation")

                route.dependant.call = must_not_run
                try:
                    response = client.request(
                        method,
                        _concrete_path(route),
                        headers=headers,
                        content=b'{"broken":',
                    )
                finally:
                    route.dependant.call = original

                _assert_safe_4xx(response)
                assert called == [], f"{method} {route.path} executed business logic"
                checked.append(f"{method} {route.path}")

    assert checked, "route inventory unexpectedly contained no protected body routes"


def test_typed_query_validation_runs_before_business_logic(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings)
    route = next(
        route
        for route in _api_routes(app)
        if route.path == f"{API_PREFIX}/sales/leads" and "GET" in (route.methods or set())
    )
    called: list[str] = []
    original = route.dependant.call

    def must_not_run(*args, **kwargs):
        called.append("handler")
        raise AssertionError("business logic ran before query validation")

    route.dependant.call = must_not_run
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                f"{API_PREFIX}/sales/leads?limit=0",
                headers={"Authorization": f"Bearer {settings.api_token}"},
            )
    finally:
        route.dependant.call = original

    assert response.status_code == 422
    _assert_safe_4xx(response)
    assert called == []


def test_public_boundaries_are_narrow_and_reject_bad_input(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        meta = client.get(f"{API_PREFIX}/meta")
        assert meta.status_code == 200
        assert settings.api_token not in meta.text

        malformed_login = client.post(
            f"{API_PREFIX}/auth/login",
            headers={"Content-Type": "application/json"},
            content=b'{"username":',
        )
        assert malformed_login.status_code == 422
        _assert_safe_4xx(malformed_login)

        bad_sns = client.post(
            f"{API_PREFIX}/email-delivery/events/ses/sns",
            json={"Type": "Notification", "MessageId": "not-signed"},
        )
        _assert_safe_4xx(bad_sns)

        bad_unsubscribe = client.get(f"{API_PREFIX}/email/unsubscribe/not-a-real-token")
        _assert_safe_4xx(bad_unsubscribe)

        logout = client.post(f"{API_PREFIX}/auth/logout", json={})
        assert logout.status_code == 200
'''
    write("tests/test_api_boundary_security.py", test_file)

    security = read("docs/SECURITY.md")
    security_addition = """

## API boundary contract (`S-06.02.02`)

The API is fail-closed. Every `/api/` route requires the configured owner token
or signed owner session unless the exact route **and HTTP method** is in the
small public policy in `api/app.py`. Public today means only metadata,
login/session/logout, one-click unsubscribe GET/POST, and the SES/SNS webhook.

Public does not mean trusted. Unsubscribe authorises with its signed token; the
SES/SNS webhook verifies the AWS envelope and expected topic; login is
rate-limited; malformed inputs are rejected before business logic.

The current product has one owner authority domain. There is no second user or
workspace whose resource could be crossed into, so this story does not invent
object-ownership rules. `S-06.01.01` owns multi-workspace identities and storage
isolation; when that story lands, its resource checks become additional
authorisation beneath this already-fail-closed API gate.
"""
    if "## API boundary contract (`S-06.02.02`)" in security:
        raise RuntimeError("SECURITY API boundary section already exists")
    write("docs/SECURITY.md", security.rstrip() + security_addition + "\n")

    changelog = read("CHANGELOG.md")
    entry = (
        "- **API boundaries now fail closed by route and HTTP method** "
        "(`S-06.02.02`). Every current protected route is swept by a negative "
        "auth test; malformed bodies are proven to fail before handlers; spoofed "
        "identity headers grant nothing; public unsubscribe/SNS boundaries retain "
        "their own token/signature checks; and the session-status endpoint no longer "
        "reports an anonymous API-token deployment as authenticated.\n"
    )
    changelog = replace_once(changelog, "## Unreleased\n\n", "## Unreleased\n\n" + entry, label="CHANGELOG S-06.02.02")
    write("CHANGELOG.md", changelog)

    defects = read("DEFECT_LOG.md")
    d51 = "| D-51 | 2026-09-18 | process | medium | TRACEABILITY.md hand-maintained status prose said 0 READY / 1 IN_REVIEW while BOARD.md had READY work and nothing in review | fixed · `S-06.02.02` removes hand-maintained status counts |\n"
    addition = d51 + (
        "| D-52 | 2026-09-18 | bug | medium | `/api/v1/auth/session` reported `authenticated: true` to an anonymous caller whenever session login was disabled, even though protected routes still required the API token | fixed · `S-06.02.02` |\n"
        "| D-53 | 2026-09-18 | security | medium | Public API exemptions were path-wide, so adding a new sensitive HTTP method under the unsubscribe prefix would silently make it anonymous | fixed · `S-06.02.02` |\n"
    )
    defects = replace_once(defects, d51, addition, label="log D-52 and D-53")
    write("DEFECT_LOG.md", defects)

    decisions = read("DECISIONS.md")
    dd20 = "| DD-20 | 2026-09-16 | A latency ceiling stops new work at operation boundaries; it does not kill an operation already in flight | The run can exceed the ceiling by the latency of one already-started operation; the overrun is measured and reported |\n"
    dd21 = dd20 + "| DD-21 | 2026-09-18 | Public API access is granted to an exact HTTP method plus path/prefix, never to a path alone | Every intentionally public new method must be added to the small policy explicitly |\n"
    decisions = replace_once(decisions, dd20, dd21, label="DD-21 table row")
    detail = """

### DD-21 — Public API access is method-specific · 2026-09-18

**The obvious thing.** Keep a list of public paths and prefixes. It is short and
the middleware already had one.

**What was done instead.** The same central middleware is kept, but each public
entry includes its HTTP method. A different method on the same path is protected
unless it is deliberately added.

**Why.** Authentication exemptions are security policy, not routing
convenience. A path-wide prefix means a future admin action nested under a
public unsubscribe path inherits anonymity without anybody making that decision.

**Cost.** Adding a legitimate public method requires one extra policy entry.

**What would make this wrong.** If FastAPI gains a route-level metadata mechanism
that can express this policy once and is available to middleware before business
logic, moving the same explicit declarations there would be cleaner.
"""
    if "### DD-21 — Public API access is method-specific" in decisions:
        raise RuntimeError("DD-21 detail already exists")
    write("DECISIONS.md", decisions.rstrip() + detail + "\n")

    trace = read("TRACEABILITY.md")
    stale = """**71 requirements, zero orphans. 26 stories are DONE, 1 is IN_REVIEW, 0 are
READY, 3 are externally BLOCKED and 24 are planned in BACKLOG.**

The board verifier recomputes the authoritative counts and acceptance coverage
from the repository. The prose here is a readable snapshot, not a substitute
for `uv run python scripts/verify_board.py`.
"""
    truthful = """Status counts are deliberately not copied into this document. `BOARD.md` is the
state authority and `uv run python scripts/verify_board.py` recomputes the live
column counts and acceptance coverage from the repository. Keeping a second
hand-maintained count here caused `D-51`.
"""
    trace = replace_once(trace, stale, truthful, label="remove stale trace counts")
    write("TRACEABILITY.md", trace)

    demo = read("DEMO.md")
    addition = """

---

## Every API endpoint authorises and validates

Run the focused boundary suite:

```bash
uv run pytest tests/test_api_boundary_security.py -q
```

The suite enumerates the live FastAPI route table rather than a hand-maintained
endpoint list. It proves every protected route/method returns `401` anonymously,
a future method under a public prefix is protected by default, malformed bodies
are rejected before their handlers execute, typed query validation runs before
business logic, spoofed identity/workspace headers grant no authority, and
public login/unsubscribe/SNS boundaries reject bad input without stack traces.

For an interactive spot-check:

```bash
curl -i http://127.0.0.1:8766/api/v1/dashboard
curl -i -H "Authorization: Bearer $OFFSETX_LOCAL_API_TOKEN" \\
  http://127.0.0.1:8766/api/v1/dashboard
```

The first request must be `401`; the second reaches the authenticated dashboard.
"""
    if "## Every API endpoint authorises and validates" in demo:
        raise RuntimeError("DEMO S-06.02.02 entry already exists")
    write("DEMO.md", demo.rstrip() + addition + "\n")


def close(implementation_sha: str, focused_summary: str, full_summary: str) -> None:
    short = implementation_sha[:7]

    board = read("BOARD.md")
    story = "- S-06.02.02 · Every endpoint authorises and validates\n"
    board = replace_once(board, story, "", label="remove S-06.02.02 from IN_PROGRESS")
    board = replace_once(
        board,
        "## IN_PROGRESS\n\n\n## IN_REVIEW",
        "## IN_PROGRESS\n\n_nothing in flight_\n\n## IN_REVIEW",
        label="restore IN_PROGRESS placeholder",
    )
    evidence = f"""- S-06.02.02 · Every endpoint authorises and validates
  tests: tests/test_api_boundary_security.py
  command: uv run pytest tests/test_api_boundary_security.py -q
  result: {focused_summary}; full Python regression {full_summary}
  live: the suite enumerates every registered /api/ route+method; anonymous protected requests are 401, a synthetic future method beneath the public unsubscribe prefix is still 401, malformed authenticated bodies never reach their handlers, spoofed identity/workspace headers grant no authority, and public callbacks reject invalid tokens/signatures without stack traces.
  code: offsetx_apollo_builder/api/app.py, tests/test_api_boundary_security.py, docs/SECURITY.md
  commit: {short}

"""
    board = replace_once(board, "## DONE\n\n", "## DONE\n\n" + evidence, label="DONE evidence")
    write("BOARD.md", board)

    trace = read("TRACEABILITY.md")
    planned = "| R-48 | S-06.02.02 | 6 | — | — |\n"
    trace = replace_once(trace, planned, "", label="remove planned R-48")
    delivered_anchor = "| R-30 | S-03.02.03 | 1 | `tests/test_browser_revoke.py` | `browser/revoke.py`, `browser/vault.py`, `browser/identity.py`, `browser/trace.py` |\n"
    delivered = delivered_anchor + (
        "| R-48 | S-06.02.02 | 6 | `tests/test_api_boundary_security.py` | `api/app.py`, `docs/SECURITY.md` |\n"
    )
    trace = replace_once(trace, delivered_anchor, delivered, label="deliver R-48")
    write("TRACEABILITY.md", trace)

    retro = read("RETRO.md")
    entry = f"""

---

## 2026-09-18 — S-06.02.02, every endpoint authorises and validates

**What was cut.** Nothing from the API-boundary story. Multi-workspace ownership
and role tiers were explicitly not absorbed because they already belong to
`S-06.01.01` and `S-06.01.02`; claiming them here would invent identities and
break change control.

**What the estimate got wrong.** Most of the authentication and body-validation
machinery already existed. The risky gaps were policy shape and proof: public
exceptions were path-wide rather than method-specific, the session-status
endpoint lied in API-token-only deployments, and there was no route-table sweep
that would fail when a new endpoint escaped auth.

**What to change next time.** For a cross-cutting invariant, enumerate the live
framework registry and test the complete set. Do not copy an endpoint list into
tests if the router can tell us the truth. Focused evidence: {focused_summary}.
Full Python regression: {full_summary}.
"""
    if "## 2026-09-18 — S-06.02.02" in retro:
        raise RuntimeError("RETRO entry already exists")
    write("RETRO.md", retro.rstrip() + entry + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: s060202_once.py pull|implement|close [...]")
    phase = sys.argv[1]
    if phase == "pull":
        pull()
    elif phase == "implement":
        implement()
    elif phase == "close":
        if len(sys.argv) != 5:
            raise SystemExit("close needs implementation_sha focused_summary full_summary")
        close(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(f"unknown phase: {phase}")
