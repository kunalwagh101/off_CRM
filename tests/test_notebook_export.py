"""Research-notebook export (§4G).

The property this file protects is not formatting. It is that an export is an
**egress path with a person as the transport**, and obeys the same rules as a
provider call:

- the destination is a trust tier, and the tier decides what survives
- the bundle is built from a declared allowlist of sections, never trimmed
- the scan runs before the first byte reaches disk, and a hit blocks everything
- mailbox content never leaves, at any tier, with any override
- what was withheld is written down, not silently absent

The second property is that nothing here assumes email. Sections declare the
campaign kinds they belong to; when image and distribution campaigns arrive the
universal sections must still export and the email-only ones must refuse with a
reason.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.notebook import (
    BUILT_IN_TARGETS,
    KEY_FILENAME,
    NEVER_EXPORTED,
    SECTIONS,
    DataClass,
    DataPolicy,
    NotebookExport,
    NotebookExportBlocked,
    NotebookExportError,
    TrustTier,
    campaign_kind,
    list_targets,
    resolve_target,
)
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore

PEOPLE = [
    ContactInput(
        full_name="Ana Silva",
        email="ana@examplecorp.com",
        company="Example Exports",
        title="Head of Trade",
        category="exporter",
        route="direct",
        public_hook="Ana Silva spoke at the EU trade summit about Example Exports",
    ),
    ContactInput(
        full_name="Bruno Costa",
        email="bruno@northport.com",
        company="Northport Freight",
        title="Operations Director",
        category="logistics",
        route="referral",
        public_hook="Northport Freight opened a Rotterdam depot",
    ),
]


@pytest.fixture()
def store(tmp_path: Path) -> OutreachStore:
    db = OutreachStore(tmp_path / "outreach.db")
    db.initialize()
    campaign_id = db.create_campaign(name="Q3 Nordic exporters", daily_send_limit=20)
    for contact in PEOPLE:
        contact_id = db.upsert_contact(contact)
        db.add_contact_to_campaign(campaign_id, contact_id)
    db.campaign_id = campaign_id  # type: ignore[attr-defined]
    yield db
    db.close()


def _export(store: OutreachStore, **kwargs) -> NotebookExport:
    return NotebookExport(store, **kwargs)


def _bundle_text(files: dict[str, str]) -> str:
    return "\n".join(files.values())


# ─────────────────────────────────────────────────────────────────────────────
# Destinations are tiers
# ─────────────────────────────────────────────────────────────────────────────


def test_notebooklm_is_tier_c_and_reaches_pseudonymous():
    """The default destination is Google's free tier, and that is not trusted.

    If this ever silently becomes B, every other test in this file still passes
    while the bundle quietly starts carrying template copy to a service whose
    terms permit training on it.
    """
    target = resolve_target("notebooklm")
    assert target.tier is TrustTier.C
    assert target.policy is DataPolicy.PSEUDONYMOUS


def test_targets_are_listed_most_restrictive_first():
    tiers = [item["tier"] for item in list_targets()]
    assert tiers == sorted(tiers, reverse=True), tiers
    assert {item["id"] for item in list_targets()} == set(BUILT_IN_TARGETS)


def test_unknown_destination_is_refused_by_name():
    with pytest.raises(NotebookExportError) as exc:
        resolve_target("notebooklm-pro")
    assert "notebooklm" in str(exc.value)


def test_raising_a_tier_needs_a_written_reason():
    with pytest.raises(NotebookExportError) as exc:
        resolve_target("notebooklm", tier_override="A")
    assert "reason" in str(exc.value).lower()

    raised = resolve_target(
        "notebooklm", tier_override="A", override_reason="Self-hosted mirror, no upload"
    )
    assert raised.tier is TrustTier.A
    assert raised.override_reason == "Self-hosted mirror, no upload"


def test_lowering_a_tier_needs_no_reason():
    """Restricting yourself further is never the decision that needs a record."""
    lowered = resolve_target("self_hosted", tier_override="C")
    assert lowered.tier is TrustTier.C
    assert lowered.override_reason == ""


def test_a_typo_in_the_tier_is_refused_rather_than_failing_to_d():
    """``coerce_tier`` fails closed to D, which is wrong for a typed argument.

    Failing closed here would produce an empty bundle and no explanation, so the
    export layer validates before coercing.
    """
    with pytest.raises(NotebookExportError) as exc:
        resolve_target("notebooklm", tier_override="Z", override_reason="typo")
    assert "A, B, C, D" in str(exc.value)


# ─────────────────────────────────────────────────────────────────────────────
# The tier decides what survives
# ─────────────────────────────────────────────────────────────────────────────


def test_tier_c_withholds_campaign_material_and_says_why(store):
    plan = _export(store).plan(store.campaign_id, resolve_target("notebooklm"))

    assert "overview" in plan.included
    assert "audience" in plan.included
    assert "people" in plan.included
    assert "templates" not in plan.included
    assert "notes" not in plan.included

    reasons = {item.section: item for item in plan.withheld}
    assert "templates" in reasons
    assert reasons["templates"].reason, "a withheld section must carry a reason"
    assert reasons["templates"].fix, "and something the owner could do about it"


def test_tier_a_carries_everything(store):
    target = resolve_target("self_hosted")
    plan = _export(store).plan(store.campaign_id, target)
    assert plan.withheld == ()
    assert set(plan.included) == {spec.id for spec in SECTIONS}


def test_internal_class_reaches_only_tier_a(store):
    exporter = _export(store)
    at_b = exporter.plan(store.campaign_id, resolve_target("hosted_notebook"))
    at_a = exporter.plan(store.campaign_id, resolve_target("self_hosted"))
    assert "notes" not in at_b.included
    assert "notes" in at_a.included


def test_no_section_carries_mailbox_content():
    """The rule is structural, not a runtime check that could be skipped.

    A section carrying MAILBOX would be gated at export time anyway, but the
    real guarantee is that no such section exists to gate.
    """
    assert all(spec.data_class is not DataClass.MAILBOX for spec in SECTIONS)
    assert any("mailbox" in item.why.lower() for item in NEVER_EXPORTED)


#: Every store method the exporter is allowed to call. The point of pinning it
#: is mailbox content: ``sent_messages``, ``last_outgoing`` and ``record_reply``
#: return message bodies, and none of them is here. Adding a reader to this set
#: is a decision someone has to make on purpose, in a diff.
ALLOWED_STORE_READS = {
    "ab_report",
    "campaign_summary",
    "get_campaign",
    "list_campaign_contacts",
    "list_templates",
    "search_memory_items",
}


def test_the_exporter_reads_only_from_an_allowlist_of_store_methods():
    """Mailbox content is unreachable structurally, not by a runtime check.

    A tier gate on a mailbox section would be the wrong control: the guarantee
    that matters is that no code path in this module can fetch a message body in
    the first place.
    """
    import ast

    source = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "notebook.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    reads: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "store"
        ):
            reads.add(node.attr)

    assert reads == ALLOWED_STORE_READS, f"store reads changed: {reads}"
    assert not (reads & {"sent_messages", "last_outgoing", "record_reply", "export_event_log"})


def test_an_override_cannot_reach_reply_text(store, tmp_path):
    """Even at tier A with a written reason, a real reply body is not exported.

    Driven through the engine so the reply is a genuine stored message rather
    than a stub — the question is whether the exporter can reach the messages
    table at all, and a fake row would not answer it.
    """
    from offsetx_apollo_builder.outreach.models import IncomingMessage

    campaign_id = store.campaign_id
    contact = store.campaign_contacts(campaign_id)[0]
    store.record_reply(
        campaign_id,
        IncomingMessage(
            provider_message_id="m-1",
            thread_id="t-1",
            from_email=contact["email"],
            subject="Re: hello",
            body_preview="SECRET-REPLY-BODY: call me Thursday about the depot",
        ),
    )
    assert store.campaign_summary(campaign_id)["contact_status"].get("replied") == 1

    target = resolve_target(
        "notebooklm", tier_override="A", override_reason="Deliberately maximal"
    )
    rendered = _export(store).render(campaign_id, target)
    assert "SECRET-REPLY-BODY" not in _bundle_text(rendered.files)


# ─────────────────────────────────────────────────────────────────────────────
# Pseudonymisation
# ─────────────────────────────────────────────────────────────────────────────


def test_tier_c_tokenises_people_including_inside_free_text(store):
    """A name in a public hook leaks exactly as hard as a name in a name field.

    "Ana Silva spoke at the EU trade summit about Example Exports" is the shape
    that defeats field-level minimisation, so the hook is scrubbed too.
    """
    rendered = _export(store).render(store.campaign_id, resolve_target("notebooklm"))
    text = _bundle_text(rendered.files)

    assert "Ana Silva" not in text
    assert "Example Exports" not in text
    assert "Bruno Costa" not in text
    assert "Northport Freight" not in text
    assert "PERSON_1" in text and "PERSON_2" in text
    assert "EU trade summit" in text, "the useful part of the hook must survive"


def test_tokens_are_distinct_per_person(store):
    """One shared PERSON_1 for everyone is not an anonymised list.

    It is a list with the answers removed, and a notebook can say nothing about
    it. Numbering per bundle is what keeps the export worth uploading.
    """
    rendered = _export(store).render(store.campaign_id, resolve_target("notebooklm"))
    people_file = rendered.files["20-people.md"]
    assert "PERSON_1" in people_file
    assert "PERSON_2" in people_file
    assert "COMPANY_1" in people_file
    assert "COMPANY_2" in people_file


def test_the_campaign_name_is_withheld_below_minimal(store):
    """A campaign name is usually the ideal customer profile written out."""
    exporter = _export(store)
    at_c = exporter.render(store.campaign_id, resolve_target("notebooklm"))
    at_a = exporter.render(store.campaign_id, resolve_target("self_hosted"))

    assert "Q3 Nordic exporters" not in _bundle_text(at_c.files)
    assert "CAMPAIGN_1" in _bundle_text(at_c.files)
    assert "Q3 Nordic exporters" in _bundle_text(at_a.files)


def test_tier_a_uses_real_names(store):
    rendered = _export(store).render(store.campaign_id, resolve_target("self_hosted"))
    text = _bundle_text(rendered.files)
    assert "Ana Silva" in text
    assert "Example Exports" in text
    assert rendered.identity_key == {}, "no key is needed when nothing is tokenised"


# ─────────────────────────────────────────────────────────────────────────────
# Addresses
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("target_id", sorted(BUILT_IN_TARGETS))
def test_no_email_address_reaches_the_bundle_at_any_tier(store, target_id):
    """Including at tier A, where the policy is ``full``.

    A research notebook has no use for addresses and a folder of them is the
    worst single artefact this system could produce, so this one is not a
    policy question.
    """
    rendered = _export(store).render(store.campaign_id, resolve_target(target_id))
    text = _bundle_text(rendered.files)
    assert "ana@examplecorp.com" not in text
    assert "bruno@northport.com" not in text


# ─────────────────────────────────────────────────────────────────────────────
# The scan runs before disk
# ─────────────────────────────────────────────────────────────────────────────


def test_a_blocked_export_writes_nothing(store, tmp_path):
    """The owner's own domain reaching a bundle blocks it, and leaves no folder.

    A partial bundle on disk is worse than no bundle at all: it is uploadable.
    """
    contact = ContactInput(
        full_name="Clara Vieira",
        email="clara@thirdparty.com",
        company="Third Party Ltd",
        public_hook="Praised offsetx.com on the Trade Lines podcast",
    )
    store.add_contact_to_campaign(store.campaign_id, store.upsert_contact(contact))

    out = tmp_path / "bundle-out"
    exporter = _export(store, owner_domains=["offsetx.com"])
    with pytest.raises(NotebookExportBlocked) as exc:
        exporter.export(store.campaign_id, resolve_target("self_hosted"), out)

    assert any(item.kind == "owner_domain" for item in exc.value.report.findings)
    assert not out.exists(), "a blocked export must leave nothing behind"


def test_an_address_in_a_template_blocks_the_export_even_at_full_policy(store, tmp_path):
    """``full`` removes field restrictions; it does not permit addresses here.

    This is the case the parametrised test above cannot reach — a contact's
    address is never read, so only text the owner wrote can carry one in.
    """
    store.upsert_template(
        {
            "id": "t-intro",
            "name": "Intro",
            "stage": "initial",
            "variant_id": "A",
            "subject_template": "Quick question",
            "body_template": "Reply to me at kunal@offsetx.example and I will send the deck.",
        }
    )
    out = tmp_path / "blocked-template"
    with pytest.raises(NotebookExportBlocked) as exc:
        _export(store).export(store.campaign_id, resolve_target("self_hosted"), out)

    assert any(item.kind == "email_address" for item in exc.value.report.findings)
    assert not out.exists()


def test_template_copy_is_exported_at_a_trusted_destination(store, tmp_path):
    """The counterpart to the block above: clean copy does go, and reads right.

    Also pins the column names — ``email_templates`` stores ``body_template``,
    not ``body``, and a reader guessing wrong produces an export of blank
    templates that looks fine until someone reads it.
    """
    store.upsert_template(
        {
            "id": "t-intro",
            "name": "Intro",
            "stage": "initial",
            "variant_id": "A",
            "subject_template": "Quick question about Rotterdam",
            "body_template": "Saw the depot news. Worth fifteen minutes?",
        }
    )
    rendered = _export(store).render(store.campaign_id, resolve_target("self_hosted"))
    templates = rendered.files["50-templates.md"]
    assert "Quick question about Rotterdam" in templates
    assert "Saw the depot news. Worth fifteen minutes?" in templates


def test_the_scan_covers_every_file_including_the_readme(store):
    rendered = _export(store).render(store.campaign_id, resolve_target("notebooklm"))
    assert rendered.scan.clean
    assert "README.md" in rendered.files
    assert "MANIFEST.json" in rendered.files


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────


def test_export_writes_a_bundle_and_keeps_the_key_outside_it(store, tmp_path):
    out = tmp_path / "aug-export"
    result = _export(store).export(store.campaign_id, resolve_target("notebooklm"), out)

    assert result.bundle_dir == out / "bundle"
    names = {item.name for item in result.files}
    assert "README.md" in names and "MANIFEST.json" in names
    assert names == {path.name for path in result.bundle_dir.iterdir()}

    assert result.key_path is not None
    assert result.key_path.parent == out
    assert result.key_path.parent != result.bundle_dir, (
        "the key must not sit in the folder the owner is told to upload"
    )
    assert result.key_path.name == KEY_FILENAME

    key = json.loads(result.key_path.read_text())
    assert key["people"]["PERSON_1"]["full_name"] in {"Ana Silva", "Bruno Costa"}


def test_the_key_is_not_written_when_nothing_is_tokenised(store, tmp_path):
    out = tmp_path / "full-export"
    result = _export(store).export(store.campaign_id, resolve_target("self_hosted"), out)
    assert result.key_path is None
    assert not (out / KEY_FILENAME).exists()


def test_export_refuses_a_directory_that_already_has_content(store, tmp_path):
    out = tmp_path / "reused"
    _export(store).export(store.campaign_id, resolve_target("notebooklm"), out)
    with pytest.raises(NotebookExportError) as exc:
        _export(store).export(store.campaign_id, resolve_target("notebooklm"), out)
    assert "not empty" in str(exc.value)


def test_manifest_digests_match_the_files_on_disk(store, tmp_path):
    """The manifest exists so the owner can prove the upload is what was built."""
    import hashlib

    out = tmp_path / "digest-check"
    result = _export(store).export(store.campaign_id, resolve_target("notebooklm"), out)
    manifest = json.loads((result.bundle_dir / "MANIFEST.json").read_text())

    for entry in manifest["files"]:
        path = result.bundle_dir / entry["name"]
        assert path.exists(), entry["name"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], entry["name"]


def test_the_readme_lists_what_was_held_back(store, tmp_path):
    out = tmp_path / "readme-check"
    result = _export(store).export(store.campaign_id, resolve_target("notebooklm"), out)
    readme = (result.bundle_dir / "README.md").read_text()
    assert "held back" in readme.lower()
    assert "Templates" in readme
    assert "Never exported" in readme


# ─────────────────────────────────────────────────────────────────────────────
# Not email-shaped
# ─────────────────────────────────────────────────────────────────────────────


def test_campaign_kind_reads_the_column(store):
    """The tripwire from before the column existed, now flipped.

    It used to assert `kind` was absent, so that the day the column landed this
    test failed and pointed at the reader. It did, and the reader needed no
    change — every path already went through `campaign_kind`.
    """
    campaign = store.get_campaign(store.campaign_id)
    assert campaign["kind"] == "email"
    assert campaign_kind(campaign) == "email"
    assert campaign_kind({"kind": "image"}) == "image"
    assert campaign_kind({}) == "email", "a row predating the column is email"


def test_an_image_campaign_gets_the_universal_sections_and_a_reason_for_the_rest(
    store, monkeypatch
):
    """The multi-kind future, exercised before the schema supports it.

    Sections that are genuinely about email must refuse by kind, not by tier —
    an image campaign has no reply rate, and telling the owner it was a trust
    decision would be a lie.
    """
    real = store.get_campaign

    def as_image(campaign_id: str):
        row = dict(real(campaign_id))
        row["kind"] = "image"
        return row

    monkeypatch.setattr(store, "get_campaign", as_image)

    plan = _export(store).plan(store.campaign_id, resolve_target("self_hosted"))
    assert plan.campaign_kind == "image"
    assert "overview" in plan.included
    assert "audience" in plan.included
    assert "people" in plan.included
    assert "what_worked" in plan.included

    by_section = {item.section: item for item in plan.withheld}
    assert set(by_section) == {"outcomes", "templates"}
    for item in by_section.values():
        assert "email" in item.reason and "image" in item.reason
        assert item.fix == "", "a kind mismatch is not something to override"


def test_kind_is_checked_before_tier(store, monkeypatch):
    """An email-only section on an image campaign says so, even at tier D.

    Otherwise the owner reads "not trusted enough" and goes looking for a
    permission problem that does not exist.
    """
    real = store.get_campaign
    monkeypatch.setattr(
        store, "get_campaign", lambda cid: {**real(cid), "kind": "distribution"}
    )
    target = resolve_target("notebooklm", tier_override="D")
    plan = _export(store).plan(store.campaign_id, target)
    templates = next(item for item in plan.withheld if item.section == "templates")
    assert "distribution" in templates.reason


def test_every_section_declares_a_class_and_a_minimum_policy():
    for spec in SECTIONS:
        assert isinstance(spec.data_class, DataClass), spec.id
        assert isinstance(spec.minimum_policy, DataPolicy), spec.id
        assert spec.filename.endswith(".md"), spec.id
        assert spec.description, f"{spec.id} must say what it is for"

    filenames = [spec.filename for spec in SECTIONS]
    assert len(set(filenames)) == len(filenames)
    assert filenames == sorted(filenames), "numbered so upload order is obvious"


def test_tier_d_receives_nothing(store):
    """The default-deny case. A destination trusted with nothing gets nothing."""
    target = resolve_target("notebooklm", tier_override="D")
    plan = _export(store).plan(store.campaign_id, target)
    assert plan.included == ()
    assert len(plan.withheld) == len(SECTIONS)


# ─────────────────────────────────────────────────────────────────────────────
# Structural
# ─────────────────────────────────────────────────────────────────────────────


def test_the_exporter_never_calls_a_provider():
    """No model writes any part of this bundle, and none is shown it.

    An export is read from the owner's own database and formatted. If a model
    ever summarised a section, the bundle would become a provider call wearing a
    file's clothes, and the tier gate above would be measuring the wrong thing.
    """
    import ast

    source = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "notebook.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(alias.name for alias in node.names)

    banned = {
        "requests",
        "httpx",
        "openai",
        "create_provider",
        "create_guarded_provider",
        "EgressBroker",
        "ModeRunner",
    }
    assert not (imported & banned), f"notebook export reaches a provider: {imported & banned}"
