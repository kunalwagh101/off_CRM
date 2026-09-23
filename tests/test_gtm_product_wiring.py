"""S-12.01.02 — everything that writes for a campaign uses its product.

The email path is exercised with the real template library and the real
audit, because "the draft is blocked" is only true if the send paths read the
same `sendable` flag these tests assert on. The post pipeline is exercised over
HTTP with the pipeline swapped for a recorder and the broker spied on, because
the property that matters is *which data class the writer was built with* —
that decision happens inside the app, before the pipeline ever runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.gtm.store import GtmStore
from offsetx_apollo_builder.locked_categories import LOCKED_CATEGORIES
from offsetx_apollo_builder.outreach.email_expert import LocalEmailExpert, route_for_category
from offsetx_apollo_builder.outreach.models import INITIAL
from offsetx_apollo_builder.outreach.store import OutreachStore
from broker_fakes import fake_model_calls

LIBRARY = Path(__file__).resolve().parents[1] / "email_expert_library" / "default_templates.json"
#: A real locked category on the client route, which `initial-client-a` serves.
CATEGORY = next(
    item for item in LOCKED_CATEGORIES if route_for_category(item) == "future_client_discovery"
)


def product_values(**overrides):
    values = {
        "name": "Ledgerline",
        "one_liner": "Reconciles freight invoices against delivery records overnight.",
        "audience": "Finance leads at logistics companies with 50 to 500 staff.",
        "problem": "Carriers overbill and nobody has time to check every invoice.",
        "offer": "a 15-minute walkthrough on your own invoices",
        "proof": ["Recovered 3.1% of freight spend at a 200-person 3PL"],
        "forbidden_claims": ["guaranteed", "100% accuracy"],
    }
    values.update(overrides)
    return values


@pytest.fixture()
def gtm(tmp_path):
    store = GtmStore(tmp_path / "gtm.db")
    yield store
    store.close()


# ── links ───────────────────────────────────────────────────────────────────


def test_links_replace_and_one_product_per_campaign(gtm):
    first = gtm.create_product("local", product_values())
    second = gtm.create_product("local", product_values(name="Second product"))

    gtm.set_links(first["id"], "local", ["c1", "c2"])
    assert gtm.product_for_campaign("c1", "local")["id"] == first["id"]
    assert sorted(gtm.linked_campaigns(first["id"], "local")) == ["c1", "c2"]

    # A campaign belongs to one product: linking it elsewhere moves it.
    gtm.set_links(second["id"], "local", ["c2"])
    assert gtm.product_for_campaign("c2", "local")["id"] == second["id"]
    assert gtm.linked_campaigns(first["id"], "local") == ["c1"]

    # The set replaces, it does not add.
    gtm.set_links(first["id"], "local", [])
    assert gtm.product_for_campaign("c1", "local") is None
    assert gtm.linked_campaigns(first["id"], "local") == []


def test_links_are_scoped_to_the_workspace_and_die_with_the_product(gtm):
    product = gtm.create_product("team-a", product_values())
    gtm.set_links(product["id"], "team-a", ["c1"])

    assert gtm.product_for_campaign("c1", "team-b") is None
    with pytest.raises(KeyError):
        gtm.set_links(product["id"], "team-b", ["c9"])

    gtm.delete_product(product["id"], "team-a")
    assert gtm.product_for_campaign("c1", "team-a") is None


# ── email templates ─────────────────────────────────────────────────────────


def _outreach(tmp_path, *, body_suffix: str):
    """A real store with the real library plus one template that uses the product."""
    store = OutreachStore(tmp_path / "outreach.db")
    store.initialize()
    expert_seed = LocalEmailExpert(store)
    expert_seed.seed_templates(LIBRARY)
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))["templates"]
    base = next(item for item in library if item["id"] == "initial-client-a")
    body = base["body_template"]
    split = body.index("\n\n") + 2
    product_template = {
        **base,
        "id": "initial-client-product",
        "variant_id": "P",
        "body_template": body[:split] + body_suffix + "\n\n" + body[split:],
    }
    store.upsert_template(product_template)
    return store


def _contact(campaign_id: str = "camp-1") -> dict[str, str]:
    return {
        "campaign_id": campaign_id,
        "full_name": "Anita Rao",
        "first_name": "Anita",
        "company": "Example Exports",
        "title": "Finance Lead",
        "category": CATEGORY,
        "route": route_for_category(CATEGORY),
        "public_hook": "Example Exports published a freight cost review",
        "hook_source": "https://example.com/review",
        "tension": "invoices and delivery records disagree",
        "questions_json": json.dumps(["Where do invoices and deliveries disagree?"]),
    }


def test_email_template_placeholders_come_from_the_linked_product(tmp_path, gtm):
    store = _outreach(tmp_path, body_suffix="We offer {product_offer}. {product_one_liner}")
    product = gtm.create_product("local", product_values())
    gtm.set_links(product["id"], "local", ["camp-1"])
    expert = LocalEmailExpert(
        store, product_reader=lambda campaign_id: gtm.product_for_campaign(campaign_id, "local")
    )

    draft = expert.create_draft(
        contact=_contact(), stage=INITIAL, variant_id="P", campaign_id="camp-1"
    )

    assert "We offer a 15-minute walkthrough on your own invoices." in draft.body
    assert "Reconciles freight invoices against delivery records overnight." in draft.body
    assert "{product" not in draft.body
    assert draft.audit.sendable, draft.audit.errors
    store.close()


def test_unlinked_campaign_renders_product_placeholders_empty_and_blocks_the_draft(tmp_path, gtm):
    store = _outreach(tmp_path, body_suffix="We offer {product_offer}.")
    expert = LocalEmailExpert(
        store, product_reader=lambda campaign_id: gtm.product_for_campaign(campaign_id, "local")
    )

    draft = expert.create_draft(
        contact=_contact("nobody-linked-this"), stage=INITIAL, variant_id="P",
        campaign_id="nobody-linked-this",
    )

    assert "{product_offer}" not in draft.body
    assert "We offer ." in draft.body
    # An email with a hole in it must not go out unattended.
    assert not draft.audit.sendable
    assert any("no product" in error.lower() for error in draft.audit.errors)
    store.close()


def test_templates_without_product_fields_render_exactly_as_before(tmp_path, gtm):
    store = _outreach(tmp_path, body_suffix="Nothing product-shaped here.")
    plain = LocalEmailExpert(store)
    wired = LocalEmailExpert(store, product_reader=lambda campaign_id: None)

    for variant in ("A", "B"):
        before = plain.create_draft(contact=_contact(), stage=INITIAL, variant_id=variant)
        after = wired.create_draft(
            contact=_contact(), stage=INITIAL, variant_id=variant, campaign_id="camp-1"
        )
        assert (after.subject, after.body) == (before.subject, before.body)
        assert after.audit.to_dict() == before.audit.to_dict()
    store.close()


def test_draft_audit_flags_a_forbidden_claim(tmp_path, gtm):
    store = _outreach(tmp_path, body_suffix="Savings are guaranteed with {product_name}.")
    product = gtm.create_product("local", product_values())
    gtm.set_links(product["id"], "local", ["camp-1"])
    expert = LocalEmailExpert(
        store, product_reader=lambda campaign_id: gtm.product_for_campaign(campaign_id, "local")
    )

    draft = expert.create_draft(
        contact=_contact(), stage=INITIAL, variant_id="P", campaign_id="camp-1"
    )
    assert not draft.audit.sendable
    assert any("guaranteed" in error for error in draft.audit.errors)

    # A person's edit is audited against the same list.
    edited = expert.audit_edited_draft(
        contact=_contact(),
        stage=INITIAL,
        variant_id="A",
        template_id="initial-client-a",
        subject=draft.subject,
        body=draft.body.replace("Savings are guaranteed", "We promise 100% accuracy"),
    )
    assert not edited.audit.sendable
    assert any("100% accuracy" in error for error in edited.audit.errors)
    store.close()


def test_product_fields_never_travel_as_recipient_data(tmp_path, gtm):
    """The older provider path sends `values` labelled as the recipient. The
    owner's product is not the recipient, so it must not appear there."""
    store = _outreach(tmp_path, body_suffix="We offer {product_offer}.")
    product = gtm.create_product("local", product_values())
    gtm.set_links(product["id"], "local", ["camp-1"])
    expert = LocalEmailExpert(
        store, product_reader=lambda campaign_id: gtm.product_for_campaign(campaign_id, "local")
    )
    seen: dict[str, object] = {}

    class Recorder:
        last_run: dict[str, object] = {}

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            seen.update(json.loads(user_prompt))
            blueprint = seen["template_blueprint"]
            return json.dumps({"subject": blueprint["subject"], "body": blueprint["body"]})

    expert.create_draft(
        contact=_contact(), stage=INITIAL, variant_id="P", campaign_id="camp-1",
        provider=Recorder(),
    )
    assert not any(key.startswith("product_") for key in seen["recipient"])
    assert "a 15-minute walkthrough" in seen["template_blueprint"]["body"]
    store.close()


# ── the post pipeline, over HTTP ────────────────────────────────────────────


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import offsetx_apollo_builder.api.app as app_module
    from offsetx_apollo_builder.api.config import AppSettings

    recorded: dict[str, list] = {"angles": [], "requests": []}

    class RecordingPipeline:
        def __init__(self, **kwargs):
            self.writer = kwargs["writer"]

        def _run(self, **kwargs):
            recorded["angles"].append(kwargs["angle"])
            self.writer("brief", f"prompt; angle={kwargs['angle']}")
            return SimpleNamespace(to_dict=lambda: {"ok": True})

        def plan(self, **kwargs):
            return self._run(**kwargs)

        def draft(self, **kwargs):
            return self._run(**kwargs)

    monkeypatch.setattr(app_module, "TrendPipeline", RecordingPipeline)
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )
    with TestClient(app_module.create_app(settings)) as client:
        def spy(request, settings, **kwargs):
            recorded["requests"].append(request)
            return SimpleNamespace(text="written")

        fake_model_calls(monkeypatch, client.app.state.ai_broker, spy)
        yield client, recorded


def _campaign(client, kind: str) -> str:
    created = client.post(
        "/api/v1/campaigns", json={"name": f"A {kind} campaign", "kind": kind, "daily_send_limit": 5}
    )
    assert created.status_code in (200, 201), created.text
    return created.json()["id"]


@pytest.mark.parametrize("step", ["plan", "draft"])
def test_product_angle_is_resolved_before_the_data_class_is_chosen(app_client, step):
    from offsetx_apollo_builder.ai.tiers import DataClass

    client, recorded = app_client
    distribution = _campaign(client, "distribution")
    product = client.post("/api/v1/gtm/products", json=product_values()).json()
    linked = client.put(
        f"/api/v1/gtm/products/{product['id']}/campaigns", json={"campaign_ids": [distribution]}
    )
    assert linked.status_code == 200, linked.text

    response = client.post(f"/api/v1/campaigns/{distribution}/pipeline/{step}", json={})
    assert response.status_code == 200, response.text

    assert recorded["angles"] == [product["one_liner"]]
    # The whole point: the owner's positioning left under the campaign class,
    # so tier C and D were never allowed to see it.
    assert recorded["requests"][-1].data_class is DataClass.CAMPAIGN


def test_an_unlinked_campaign_keeps_the_public_path(app_client):
    from offsetx_apollo_builder.ai.tiers import DataClass

    client, recorded = app_client
    distribution = _campaign(client, "distribution")
    client.post(f"/api/v1/campaigns/{distribution}/pipeline/plan", json={})
    assert recorded["angles"] == [""]
    assert recorded["requests"][-1].data_class is DataClass.PUBLIC


def test_explicit_angle_wins(app_client):
    client, recorded = app_client
    distribution = _campaign(client, "distribution")
    product = client.post("/api/v1/gtm/products", json=product_values()).json()
    linked = client.put(
        f"/api/v1/gtm/products/{product['id']}/campaigns", json={"campaign_ids": [distribution]}
    )
    assert linked.status_code == 200, linked.text
    client.post(f"/api/v1/campaigns/{distribution}/pipeline/plan", json={"angle": "Typed today"})
    assert recorded["angles"] == ["Typed today"]


def test_linking_an_unknown_campaign_is_refused(app_client):
    client, _ = app_client
    product = client.post("/api/v1/gtm/products", json=product_values()).json()
    refused = client.put(
        f"/api/v1/gtm/products/{product['id']}/campaigns", json={"campaign_ids": ["no-such"]}
    )
    assert refused.status_code == 422
    assert refused.json()["detail"]["error"] == "unknown_campaign"
    listed = client.get(f"/api/v1/gtm/products/{product['id']}/campaigns").json()
    assert listed["items"] == []


# ── the automation timer ────────────────────────────────────────────────────


def test_automation_resolves_the_product_angle(tmp_path):
    from offsetx_apollo_builder.distribution.automation import ContentAutomationService

    factory_angles: list[str] = []
    run_angles: list[str] = []

    class Runner:
        def plan(self, **kwargs):
            run_angles.append(kwargs["angle"])
            return SimpleNamespace(to_dict=lambda: {})

        def draft(self, **kwargs):
            run_angles.append(kwargs["angle"])
            return SimpleNamespace(to_dict=lambda: {})

    def factory(angle: str) -> Runner:
        factory_angles.append(angle)
        return Runner()

    service = ContentAutomationService(
        tmp_path / "content_automation.json",
        trends_factory=lambda: None,
        pipeline_factory=factory,
        distribution_factory=lambda: None,
        angle_resolver=lambda campaign_id, declared: declared or f"product of {campaign_id}",
    )
    pipeline = {
        "distribution_campaign_id": "dist-1",
        "image_campaign_id": "img-1",
        "angle": "",
        "account_ids": [],
    }
    config = {"max_topics": 1, "candidates": 1}
    assert service._plan(config, pipeline)["status"] == "ok"
    assert service._draft(config, pipeline)["status"] == "ok"
    # The factory chooses the data class from the angle it is handed, so it
    # must receive the resolved one — not the empty declared one.
    assert factory_angles == ["product of dist-1", "product of dist-1"]
    assert run_angles == ["product of dist-1", "product of dist-1"]


def test_automation_without_a_resolver_behaves_as_before(tmp_path):
    from offsetx_apollo_builder.distribution.automation import ContentAutomationService

    seen: list[str] = []

    class Runner:
        def plan(self, **kwargs):
            return SimpleNamespace(to_dict=lambda: {})

    def factory(angle: str) -> Runner:
        seen.append(angle)
        return Runner()

    service = ContentAutomationService(
        tmp_path / "content_automation.json",
        trends_factory=lambda: None,
        pipeline_factory=factory,
        distribution_factory=lambda: None,
    )
    pipeline = {"distribution_campaign_id": "d", "image_campaign_id": "i", "angle": "Declared", "account_ids": []}
    service._plan({"max_topics": 1, "candidates": 1}, pipeline)
    assert seen == ["Declared"]


def test_a_campaign_linked_in_another_workspace_cannot_be_taken(gtm):
    theirs = gtm.create_product("team-a", product_values())
    gtm.set_links(theirs["id"], "team-a", ["shared-id"])
    ours = gtm.create_product("team-b", product_values())
    gtm.set_links(ours["id"], "team-b", ["mine"])

    with pytest.raises(KeyError):
        gtm.set_links(ours["id"], "team-b", ["mine", "shared-id"])

    assert gtm.product_for_campaign("shared-id", "team-a")["id"] == theirs["id"]
    # The refusal rolled back: our existing link survived the failed replace.
    assert gtm.linked_campaigns(ours["id"], "team-b") == ["mine"]


def test_every_engine_is_built_with_products():
    """An engine built without the product reader fills `{product_offer}` with a
    blank. The audit would block those drafts, but every draft from that engine
    would be blocked for a wiring slip. So every `OutreachEngine(...)` in the
    app must be the first argument of `_attach_products(...)`."""
    import ast

    source = (Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "api" / "app.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    wrapped: set[int] = set()
    built: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "OutreachEngine":
            built.append(node.lineno)
        if node.func.id == "_attach_products" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
                if first.func.id == "OutreachEngine":
                    wrapped.add(first.lineno)
    assert built, "no OutreachEngine construction found; the test is looking at the wrong file"
    bare = sorted(set(built) - wrapped)
    assert not bare, f"OutreachEngine built without _attach_products at app.py lines {bare}"


def test_a_template_can_say_the_angle_and_gets_the_one_liner_without_a_plan(gtm):
    """`{product_angle}` is the applied plan's angle for this campaign; a campaign
    linked by hand, with no plan, gets the product's one-liner."""
    from offsetx_apollo_builder.outreach.email_expert import _product_fields

    product = gtm.create_product("local", product_values())
    gtm.set_links(product["id"], "local", ["c1"])
    linked = gtm.product_for_campaign("c1", "local")
    assert linked["angle"] == product["one_liner"]
    assert _product_fields(linked)["product_angle"] == product["one_liner"]
    assert _product_fields(None)["product_angle"] == ""


# ── acting for a campaign, not for a signed-in person (D-109) ───────────────


def test_a_link_made_from_a_workspace_login_is_found_by_the_campaign(gtm):
    """The engine and the timers act for a campaign and have no login.

    Before, they asked with the install's workspace and found nothing for a
    campaign linked from any other workspace — its drafts lost the product and
    its forbidden claims went unchecked.
    """
    product = gtm.create_product("acme", product_values())
    gtm.set_links(product["id"], "acme", ["camp-9"])

    found = gtm.product_for_linked_campaign("camp-9")
    assert found["id"] == product["id"]
    assert found["angle"] == product["one_liner"]
    # Scoped reads are unchanged: another workspace still cannot see it.
    assert gtm.product_for_campaign("camp-9", "local") is None
    assert gtm.product_for_linked_campaign("never-linked") is None


def test_the_engine_reads_the_product_linked_from_another_workspace(app_client):
    client, _ = app_client
    campaign = _campaign(client, "email")
    store = client.app.state.gtm_store
    product = store.create_product("acme", product_values())
    store.set_links(product["id"], "acme", [campaign])

    reader = client.app.state.engine.email_expert.product_reader
    assert reader(campaign)["id"] == product["id"]


def test_the_content_timer_builds_its_engines_without_a_login(app_client):
    """A timer has no cookies. Building the pipeline for it used to raise
    AttributeError before a single post was planned."""
    client, _ = app_client
    automation = client.app.state.content_automation
    assert automation.pipeline_factory("") is not None
    assert automation.distribution_factory() is not None
