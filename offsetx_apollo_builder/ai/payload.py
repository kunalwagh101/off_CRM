"""Payload construction.

Section 5.5.2 of the build brief: *build* each payload from an explicit allowlist
of fields; never take an internal object and strip fields from it, because a
field you forget to strip is a leak.

So every function here starts from an empty dict and adds only what the active
:class:`~offsetx_apollo_builder.ai.tiers.DataPolicy` permits.  The input types
are deliberately narrow — you cannot pass a CRM row straight in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .tiers import DataClass, DataPolicy

#: Recipients are referred to by an opaque token.  off_CRM re-attaches the real
#: address locally after generation; a model never needs one to write an email.
RECIPIENT_TOKEN = "RECIPIENT_1"
SENDER_TOKEN = "SENDER"

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


@dataclass(slots=True)
class PersonPublic:
    """The public professional facts about one person.

    This is the *only* person-shaped object the broker accepts.  It has no email
    field on purpose — an address cannot reach a payload through this path even
    by mistake, because there is nowhere to put one.
    """

    full_name: str = ""
    first_name: str = ""
    title: str = ""
    company: str = ""
    category: str = ""
    route: str = ""
    public_hook: str = ""
    hook_source: str = ""
    linkedin_url: str = ""
    tension: str = ""
    contribution: str = ""
    questions: list[str] = field(default_factory=list)

    @classmethod
    def from_contact(cls, contact: dict[str, Any]) -> "PersonPublic":
        """Build from a CRM contact row, copying across only public fields.

        Note the direction: this reads named keys out of ``contact``.  It does
        not copy the row and delete keys, so a new column added to the contacts
        table can never appear in a payload without someone editing this method.
        """
        questions = [
            str(contact.get(key, "")).strip()
            for key in ("question_1", "question_2", "question_3")
            if str(contact.get(key, "")).strip()
        ]
        return cls(
            full_name=str(contact.get("full_name", "")).strip(),
            first_name=str(contact.get("first_name", "")).strip(),
            title=str(contact.get("title", "")).strip(),
            company=str(contact.get("company", "")).strip(),
            category=str(contact.get("category", "")).strip(),
            route=str(contact.get("route", "")).strip(),
            public_hook=str(contact.get("public_hook", "")).strip(),
            hook_source=str(contact.get("hook_source", "")).strip(),
            linkedin_url=str(contact.get("linkedin_url", "")).strip(),
            tension=str(contact.get("tension", "")).strip(),
            contribution=str(contact.get("contribution", "")).strip(),
            questions=questions,
        )


@dataclass(slots=True)
class EgressRequest:
    """Everything a caller may offer the broker.

    Offering is not sending.  The payload builder decides which of these fields
    actually leave, based on the resolved policy.
    """

    task_type: str
    data_class: DataClass
    instructions: str = ""
    person: PersonPublic | None = None
    positioning_line: str = ""
    template_text: str = ""
    campaign_notes: str = ""
    public_text: str = ""
    prior_drafts: list[dict[str, str]] = field(default_factory=list)
    conversation: list[dict[str, str]] = field(default_factory=list)
    unrestricted: dict[str, Any] = field(default_factory=dict)
    task_tags: tuple[str, ...] = ()


def _clean(value: object, limit: int = 2000) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def tokenise_addresses(text: str) -> str:
    """Replace any email address with the recipient token.

    Used on free text that the owner typed, where an address may appear inline.
    The pre-flight scanner still runs afterwards — this reduces false alarms on
    legitimate text, it does not replace the check.
    """
    return _EMAIL_RE.sub(f"<{RECIPIENT_TOKEN}>", str(text or ""))


def _person_fields(person: PersonPublic, policy: DataPolicy) -> dict[str, Any]:
    """Person fields permitted at each policy level.

    ``strict``  — nothing that identifies the individual.
    ``minimal`` — their public professional identity, which is what enrichment
                  and personalisation actually need (owner's instruction).
    ``standard``/``full`` — adds the public hook's source and profile URL.
    """
    built: dict[str, Any] = {}

    # Present at every level: structural fields that describe the *slot*, not
    # the person. These identify nobody on their own.
    for key, value in (
        ("category", person.category),
        ("route", person.route),
        ("tension", person.tension),
        ("contribution", person.contribution),
    ):
        cleaned = _clean(value, 500)
        if cleaned:
            built[key] = cleaned
    questions = [_clean(item, 300) for item in person.questions if _clean(item, 300)]
    if questions:
        built["questions"] = questions[:3]

    if policy.rank <= DataPolicy.STRICT.rank:
        return built

    # minimal and above: the public professional identity.
    for key, value in (
        ("full_name", person.full_name),
        ("first_name", person.first_name),
        ("title", person.title),
        ("company", person.company),
        ("public_hook", person.public_hook),
    ):
        cleaned = _clean(value, 600)
        if cleaned:
            built[key] = cleaned

    if policy.rank >= DataPolicy.STANDARD.rank:
        for key, value in (
            ("hook_source", person.hook_source),
            ("linkedin_url", person.linkedin_url),
        ):
            cleaned = _clean(value, 400)
            if cleaned:
                built[key] = cleaned

    return built


def build_payload(request: EgressRequest, policy: DataPolicy) -> dict[str, Any]:
    """Construct the outbound payload from an empty dict.

    Every ``built[...] = ...`` below is a deliberate decision to let one field
    leave.  There is no path that copies an object wholesale except ``full``,
    which the owner opts into per provider and which the scanner still inspects.
    """
    built: dict[str, Any] = {
        "schema_version": 1,
        "task": _clean(request.task_type, 120),
        "recipient_token": RECIPIENT_TOKEN,
        "sender_token": SENDER_TOKEN,
    }

    instructions = _clean(request.instructions, 6000)
    if instructions:
        built["instructions"] = tokenise_addresses(instructions)

    if request.person is not None:
        person_fields = _person_fields(request.person, policy)
        if person_fields:
            built["recipient"] = person_fields

    # The owner's public one-liner is the only sender-side content permitted to
    # leave below `full` (§5.2 item 2).
    positioning = _clean(request.positioning_line, 500)
    if positioning and policy.rank >= DataPolicy.MINIMAL.rank:
        built["sender_positioning"] = tokenise_addresses(positioning)

    if policy.rank >= DataPolicy.STANDARD.rank:
        template = _clean(request.template_text, 12000)
        if template:
            built["template"] = tokenise_addresses(template)
        notes = _clean(request.campaign_notes, 4000)
        if notes:
            built["campaign_notes"] = tokenise_addresses(notes)
        if request.prior_drafts:
            built["prior_drafts"] = [
                {
                    "subject": tokenise_addresses(_clean(item.get("subject"), 300)),
                    "body": tokenise_addresses(_clean(item.get("body"), 4000)),
                }
                for item in request.prior_drafts[:3]
            ]

    # Public, non-personal material is safe at every level — that is what makes
    # a tier C or public-only provider useful at all.
    public_text = _clean(request.public_text, 20000)
    if public_text:
        built["public_context"] = tokenise_addresses(public_text)

    if request.conversation:
        limit = 20 if policy.rank >= DataPolicy.STANDARD.rank else 6
        built["conversation"] = [
            {
                "role": _clean(turn.get("role"), 20),
                "content": tokenise_addresses(_clean(turn.get("content"), 8000)),
            }
            for turn in request.conversation[-limit:]
        ]

    if policy is DataPolicy.FULL and request.unrestricted:
        # Explicit owner opt-in for one provider. Still scanned, still logged.
        built["unrestricted"] = request.unrestricted

    return built


def payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Small structural description for the egress log index.

    Cheap to store for every call, unlike the payload itself.
    """
    recipient = payload.get("recipient")
    return {
        "fields": sorted(payload.keys()),
        "recipient_fields": sorted(recipient.keys()) if isinstance(recipient, dict) else [],
        "character_count": len(str(payload)),
        "has_unrestricted": "unrestricted" in payload,
    }


def describe_policy_for_class(policy: DataPolicy, data_class: DataClass) -> str:
    """One plain sentence for the UI: what will actually be sent."""
    if data_class is DataClass.PUBLIC:
        return "Public, non-personal content only. No person is named."
    if policy is DataPolicy.STRICT:
        return "Category and question structure only. Nobody is identifiable."
    if policy is DataPolicy.MINIMAL:
        return (
            "The person's public name, company, title and public hook, plus your "
            "one-line positioning. No email addresses, no template, no notes."
        )
    if policy is DataPolicy.STANDARD:
        return (
            "The above plus your template text and campaign notes. Email addresses "
            "are still replaced by tokens."
        )
    return (
        "No field restrictions. Real email addresses and internal notes can leave. "
        "Every call is still scanned and logged."
    )
