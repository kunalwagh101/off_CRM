from __future__ import annotations

import json

from offsetx_apollo_builder.locked_categories import LOCKED_CATEGORIES
from offsetx_apollo_builder.outreach.email_expert import (
    FOLLOWUP_1_REQUIRED,
    FOLLOWUP_2_REQUIRED,
    LocalEmailExpert,
    OFFSETX_SIGNATURE,
    audit_draft,
    route_for_category,
)
from offsetx_apollo_builder.outreach.models import FOLLOWUP_1, FOLLOWUP_2, INITIAL
from offsetx_apollo_builder.outreach.store import OutreachStore


def _contact(category: str) -> dict[str, str]:
    return {
        "full_name": "Anita Rao",
        "first_name": "Anita",
        "email": "anita@example.com",
        "company": "Example Exports",
        "title": "Climate Lead",
        "category": category,
        "route": route_for_category(category),
        "public_hook": "Example Exports published a supplier emissions brief",
        "hook_source": "https://example.com/brief",
        "tension": "supplier evidence changes across teams",
        "questions_json": json.dumps(["Where does evidence break?"]),
    }


def test_all_locked_categories_and_variants_produce_sendable_sequences(tmp_path):
    store = OutreachStore(tmp_path / "outreach.db")
    store.initialize()
    expert = LocalEmailExpert(store)
    expert.seed_templates("email_expert_library/default_templates.json")

    for category in LOCKED_CATEGORIES:
        for variant in ("A", "B"):
            initial = expert.create_draft(
                contact=_contact(category), stage=INITIAL, variant_id=variant
            )
            followup1 = expert.create_draft(
                contact=_contact(category),
                stage=FOLLOWUP_1,
                variant_id=variant,
                original_subject=initial.subject,
            )
            followup2 = expert.create_draft(
                contact=_contact(category),
                stage=FOLLOWUP_2,
                variant_id=variant,
                original_subject=initial.subject,
            )
            assert initial.audit.sendable, initial.audit.errors
            assert followup1.audit.sendable, followup1.audit.errors
            assert followup2.audit.sendable, followup2.audit.errors
            assert initial.body.count("?") == 1
            assert FOLLOWUP_1_REQUIRED in followup1.body
            assert FOLLOWUP_2_REQUIRED in followup2.body
            assert "—" not in initial.body + followup1.body + followup2.body
    store.close()


def test_missing_hook_source_and_manipulative_language_are_blocked():
    body = f"""Hi Anita,

Example Exports published a supplier emissions brief. This is enough context to make this body deliberately long enough for the length guard while we test the stricter sourcing and language rules in a realistic first-touch message for an operator working on climate evidence and handoffs.

Would a quick call help?

{OFFSETX_SIGNATURE}"""
    audit = audit_draft(
        stage=INITIAL,
        route="future_client_discovery",
        category=LOCKED_CATEGORIES[0],
        public_hook="Published supplier brief",
        hook_source="",
        subject="Evidence question",
        body=body,
    )
    assert not audit.sendable
    assert "A public hook source is required" in audit.errors
    assert any("quick call" in error for error in audit.errors)


def test_ai_escaped_paragraph_breaks_are_real_newlines():
    from offsetx_apollo_builder.outreach.email_expert import normalize_email_body

    # A provider can return double-encoded JSON strings. These must not enter
    # a prospect's outbox as the visible characters backslash and n.
    rendered = (
        "Hi Anita," + r"\n\n"
        + "I read your public supplier briefing." + r"\n\n"
        + "Would the evidence workflow be useful?" + r"\n\n"
        + OFFSETX_SIGNATURE.replace("\n", r"\n")
    )
    cleaned = normalize_email_body(rendered)
    assert r"\n" not in cleaned
    assert "Hi Anita,\n\nI read" in cleaned
    assert OFFSETX_SIGNATURE in cleaned


def test_literal_escaped_newlines_are_never_sendable_without_normalization():
    audit = audit_draft(
        stage=INITIAL,
        route=route_for_category(LOCKED_CATEGORIES[0]),
        category=LOCKED_CATEGORIES[0],
        public_hook="Public supplier briefing",
        hook_source="https://example.com/brief",
        subject="Supplier evidence",
        body="Hi Anita," + r"\n\n" + "Any thoughts?" + r"\n\n"
        + OFFSETX_SIGNATURE.replace("\n", r"\n"),
    )
    assert not audit.sendable
    assert any("escaped" in item.lower() for item in audit.errors)


def test_draft_audit_blocks_missing_greeting_and_double_full_stop():
    common = dict(
        stage=INITIAL,
        route=route_for_category(LOCKED_CATEGORIES[0]),
        category=LOCKED_CATEGORIES[0],
        public_hook="Public supplier briefing",
        hook_source="https://example.com/brief",
        subject="Supplier evidence",
    )
    no_greeting = audit_draft(
        **common,
        body="I read your public supplier update.\n\nWould this help?\n\n"
        + OFFSETX_SIGNATURE,
    )
    double_dot = audit_draft(
        **common,
        body="Hi Anita,\n\nI saw your October.. update.\n\n"
        "Would this help?\n\n" + OFFSETX_SIGNATURE,
    )
    assert not no_greeting.sendable
    assert any("greeting" in item.lower() for item in no_greeting.errors)
    assert not double_dot.sendable
    assert any("punctuation" in item.lower() for item in double_dot.errors)
