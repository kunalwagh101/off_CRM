"""S-12.01.01 — the owner records the product once.

Each acceptance criterion in `PRODUCT_BACKLOG.md` maps to a test below, named
for the behaviour rather than the function. The store is exercised against a
real SQLite file and the API against the real app, because a product that
validates in a unit test and then fails to round-trip through JSON is exactly
the bug a mock would hide.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from offsetx_apollo_builder.gtm.products import (
    LABELS,
    ProductInvalid,
    find_forbidden,
    validate_product,
)
from offsetx_apollo_builder.gtm.store import GtmStore

GTM = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "gtm"


def good(**overrides):
    values = {
        "name": "Ledgerline",
        "one_liner": "Reconciles freight invoices against delivery records overnight.",
        "audience": "Finance leads at logistics companies with 50 to 500 staff.",
        "problem": "Carriers overbill by 2-4% and nobody has time to check every invoice.",
        "outcome": "Overbilling is caught before payment, not after audit.",
        "offer": "A 15-minute walkthrough on your own invoices",
        "proof": ["Recovered 3.1% of freight spend at a 200-person 3PL"],
        "differentiators": ["Reads PDF invoices without a template"],
        "forbidden_claims": ["guaranteed", "100% accuracy"],
        "voice": "Plain, specific, no hype.",
        "website": "https://ledgerline.example",
    }
    values.update(overrides)
    return values


@pytest.fixture()
def store(tmp_path):
    opened = GtmStore(tmp_path / "gtm.db")
    yield opened
    opened.close()


# ── criterion 1: stored at version 1 and read back identically ──────────────


def test_a_product_is_created_at_version_one_and_read_back(store):
    created = store.create_product("local", good())

    assert created["version"] == 1
    assert created["id"]
    read = store.get_product(created["id"], "local")
    assert read == created
    for key, value in good().items():
        assert read[key] == value
    assert [item["id"] for item in store.list_products("local")] == [created["id"]]


def test_whitespace_is_collapsed_and_list_duplicates_removed(store):
    created = store.create_product(
        "local",
        good(
            name="  Ledgerline  ",
            problem="Carriers   overbill\n\nby 2-4% and nobody has time to check.",
            proof=["Saved 3%", "saved 3%", "  Saved   3%  ", "Another result"],
        ),
    )
    assert created["name"] == "Ledgerline"
    assert created["problem"] == "Carriers overbill by 2-4% and nobody has time to check."
    assert created["proof"] == ["Saved 3%", "Another result"]


# ── criterion 2: bad input is refused with the field named ──────────────────


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "x" * 81}, "name"),
        ({"one_liner": "too short"}, "one_liner"),
        ({"audience": ""}, "audience"),
        ({"problem": "short"}, "problem"),
        ({"offer": "no"}, "offer"),
        ({"offer": "x" * 201}, "offer"),
        ({"outcome": "x" * 601}, "outcome"),
        ({"website": "ftp://ledgerline.example"}, "website"),
        ({"website": "https://"}, "website"),
        ({"website": "not a url"}, "website"),
        ({"proof": ["ok result"] * 3 + [f"result {i}" for i in range(8)]}, "proof"),
        ({"forbidden_claims": ["x"]}, "forbidden_claims"),
        ({"proof": "a string, not a list"}, "proof"),
    ],
)
def test_bad_input_is_refused_with_the_field_named(store, overrides, field):
    with pytest.raises(ProductInvalid) as refused:
        store.create_product("local", good(**overrides))
    assert refused.value.field == field
    assert LABELS[field] in str(refused.value)
    assert store.list_products("local") == []


def test_a_missing_required_field_is_refused(store):
    values = good()
    del values["offer"]
    with pytest.raises(ProductInvalid) as refused:
        store.create_product("local", values)
    assert refused.value.field == "offer"


def test_an_unknown_field_is_refused_rather_than_dropped(store):
    with pytest.raises(ProductInvalid) as refused:
        store.create_product("local", good(pricing="secret"))
    assert refused.value.field == "pricing"


# ── criterion 3: an address never gets in ───────────────────────────────────


@pytest.mark.parametrize(
    "overrides",
    [
        {"offer": "Email founder@ledgerline.example for a walkthrough"},
        {"proof": ["Ask ops@carrier.example how much we saved them"]},
        {"voice": "Sign off as hello@ledgerline.example"},
    ],
)
def test_an_email_address_is_refused_at_the_door(store, overrides):
    with pytest.raises(ProductInvalid) as refused:
        store.create_product("local", good(**overrides))
    assert "address" in str(refused.value).lower()
    assert "model" in str(refused.value).lower()


# ── criterion 4: an edit raises the version by exactly one ──────────────────


def test_an_edit_raises_the_version(store):
    created = store.create_product("local", good())
    edited = store.update_product(created["id"], "local", {"offer": "A free invoice audit"})
    assert edited["version"] == 2
    assert edited["offer"] == "A free invoice audit"
    assert edited["name"] == created["name"]

    again = store.update_product(created["id"], "local", {"voice": "Warmer."})
    assert again["version"] == 3


def test_a_bad_edit_changes_nothing(store):
    created = store.create_product("local", good())
    with pytest.raises(ProductInvalid):
        store.update_product(created["id"], "local", {"one_liner": "short"})
    assert store.get_product(created["id"], "local") == created


def test_an_empty_edit_is_refused_rather_than_bumping_the_version(store):
    created = store.create_product("local", good())
    with pytest.raises(ProductInvalid):
        store.update_product(created["id"], "local", {})
    assert store.get_product(created["id"], "local")["version"] == 1


# ── criterion 5: forbidden claims, matched as whole phrases ─────────────────


def test_forbidden_claims_match_whole_phrases_including_percent():
    claims = ["guaranteed", "100% accuracy", "No risk"]

    assert find_forbidden("Results GUARANTEED within a week.", claims) == ["guaranteed"]
    # `\b` never matches after `%` — the bug that let a margin leak through
    # ai/abstraction.py. The phrase must still be found.
    assert find_forbidden("We promise 100% accuracy.", claims) == ["100% accuracy"]
    assert find_forbidden("no   risk at all", claims) == ["No risk"]
    # Not inside a longer word, at either end.
    assert find_forbidden("Returns are unguaranteed.", claims) == []
    assert find_forbidden("guaranteedly", claims) == []
    assert find_forbidden("1100% accuracy", claims) == []
    assert find_forbidden("", claims) == []
    assert find_forbidden("anything", []) == []


def test_validation_is_pure_and_partial_updates_skip_absent_fields():
    cleaned = validate_product({"voice": "  Calm.  "}, partial=True)
    assert cleaned == {"voice": "Calm."}
    with pytest.raises(ProductInvalid):
        validate_product({"voice": "Calm."})


# ── criterion 6: one workspace cannot reach another's product ───────────────


def test_another_workspace_cannot_see_the_product(store):
    created = store.create_product("team-a", good())

    assert store.list_products("team-b") == []
    with pytest.raises(KeyError):
        store.get_product(created["id"], "team-b")
    with pytest.raises(KeyError):
        store.update_product(created["id"], "team-b", {"voice": "x"})
    with pytest.raises(KeyError):
        store.delete_product(created["id"], "team-b")
    assert store.get_product(created["id"], "team-a")["version"] == 1


def test_delete_removes_the_product(store):
    created = store.create_product("local", good())
    store.delete_product(created["id"], "local")
    assert store.list_products("local") == []
    with pytest.raises(KeyError):
        store.get_product(created["id"], "local")


def test_the_store_survives_a_reopen(tmp_path):
    first = GtmStore(tmp_path / "gtm.db")
    created = first.create_product("local", good())
    first.close()
    second = GtmStore(tmp_path / "gtm.db")
    try:
        assert second.get_product(created["id"], "local") == created
    finally:
        second.close()


# ── over HTTP, through the real app ─────────────────────────────────────────


@pytest.fixture()
def client(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )
    with TestClient(create_app(settings)) as opened:
        yield opened


def test_the_product_round_trips_over_http(client):
    created = client.post("/api/v1/gtm/products", json=good())
    assert created.status_code == 201, created.text
    product = created.json()
    assert product["version"] == 1

    listed = client.get("/api/v1/gtm/products").json()
    assert [item["id"] for item in listed["items"]] == [product["id"]]
    assert client.get(f"/api/v1/gtm/products/{product['id']}").json() == product

    edited = client.patch(f"/api/v1/gtm/products/{product['id']}", json={"offer": "A free audit"})
    assert edited.status_code == 200
    assert edited.json()["version"] == 2

    deleted = client.delete(f"/api/v1/gtm/products/{product['id']}")
    assert deleted.json() == {"deleted": True}
    assert client.get("/api/v1/gtm/products").json()["items"] == []


def test_http_refusals_are_sentences_not_stack_traces(client):
    refused = client.post("/api/v1/gtm/products", json=good(website="ftp://x.example"))
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["error"] == "invalid_product"
    assert detail["field"] == "website"
    assert detail["message"].endswith(".")

    missing = client.get("/api/v1/gtm/products/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"] == "not_found"

    assert client.patch("/api/v1/gtm/products/nope", json={"voice": "x"}).status_code == 404
    assert client.delete("/api/v1/gtm/products/nope").status_code == 404

    not_an_object = client.post("/api/v1/gtm/products", json=["a", "list"])
    assert not_an_object.status_code == 422


# ── the module owns no transport and reaches no model ───────────────────────

#: Nothing in `gtm` may reach a provider, the broker or the network. `ask` is
#: injected, the way the video director's is.
FORBIDDEN_IMPORTS = (
    # All of ai/, not three modules of it: `ai/__init__` imports the broker, so
    # importing anything under `ai` loads it.
    "offsetx_apollo_builder.ai",
    "offsetx_apollo_builder.outreach.providers",
    "offsetx_apollo_builder.outreach.provider_profiles",
    "offsetx_apollo_builder.apollo_client",
    "httpx",
    "requests",
    "urllib.request",
    "socket",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                # Resolve `from ..ai import broker` relative to the gtm package.
                parts = ["offsetx_apollo_builder", "gtm"][: 2 - (node.level - 1)]
                base = ".".join(parts + ([base] if base else []))
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def test_gtm_owns_no_transport():
    modules = sorted(GTM.glob("*.py"))
    assert modules, "the gtm package has no modules"
    for module in modules:
        imported = _imports(module)
        for forbidden in FORBIDDEN_IMPORTS:
            hits = [name for name in imported if name == forbidden or name.startswith(forbidden + ".")]
            assert not hits, f"{module.name} imports {hits}; gtm must stay transport-free"


def test_nothing_gtm_loads_reaches_a_model_or_the_network():
    """The AST walk sees only direct imports. This loads the package in a clean
    interpreter and looks at everything that came with it."""
    import subprocess
    import sys

    probe = (
        "import sys\n"
        "import offsetx_apollo_builder.gtm.service, offsetx_apollo_builder.gtm.review\n"
        "bad = sorted(m for m in sys.modules if m == 'offsetx_apollo_builder.ai' "
        "or m.startswith('offsetx_apollo_builder.ai.') or m in ('httpx', 'requests', "
        "'urllib.request', 'offsetx_apollo_builder.apollo_client'))\n"
        "print(','.join(bad))\n"
    )
    loaded = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert loaded.stdout.strip() == ""


def test_products_module_is_pure():
    imported = _imports(GTM / "products.py")
    assert not any(name.startswith("offsetx_apollo_builder.db") for name in imported)
    assert not any(name.startswith("offsetx_apollo_builder.ai") for name in imported)
    assert "sqlite3" not in imported


def test_address_pattern_matches_the_scanners():
    """What the product form refuses is exactly what the scanner would block."""
    from offsetx_apollo_builder.ai import scanner
    from offsetx_apollo_builder.gtm import products

    assert products.ADDRESS.pattern == scanner._EMAIL_RE.pattern
    assert products.ADDRESS.flags == scanner._EMAIL_RE.flags


def test_a_stale_version_is_a_conflict_not_a_lost_update(store):
    """The Postgres case, driven directly: an edit written against a version the
    row no longer has must be refused, not applied over the newer edit."""
    from offsetx_apollo_builder.gtm.products import FIELDS
    from offsetx_apollo_builder.gtm.store import ProductConflict

    created = store.create_product("local", good())
    store.update_product(created["id"], "local", {"voice": "Newer."})
    merged = {field: created[field] for field in FIELDS}
    with pytest.raises(ProductConflict):
        with store.connection.transaction() as db:
            store._write(db, created["id"], "local", merged, expected_version=1)
    assert store.get_product(created["id"], "local")["voice"] == "Newer."
