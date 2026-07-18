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
