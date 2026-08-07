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

#: Identity tokens for ``pseudonymous``.  A request carries exactly one person,
#: so these are constant rather than allocated — there is no mapping table to
#: keep, and nothing to leak.  off_CRM knows who the request was about and puts
#: the real values back after generation, the same way it does for addresses.
PERSON_TOKEN = "PERSON_1"
COMPANY_TOKEN = "COMPANY_1"

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

#: Below this length a name is too generic to remove without destroying the
#: sentence around it — "Ed" would eat "edge", "Li" would eat "link".
_MIN_SCRUBBABLE = 3


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


def _identity_terms(person: PersonPublic) -> list[tuple[str, str]]:
    """``(term, replacement)`` pairs for scrubbing this person out of free text.

    Longest first, so "Ana Silva" is consumed before the "Ana" rule can turn it
    into "PERSON_1 Silva".  This is *targeted* removal, not guesswork: off_CRM
    knows exactly who the request is about, which is the same reason the recall
    index can redact precisely instead of pattern-matching for names.
    """
    surname = ""
    parts = str(person.full_name or "").split()
    if len(parts) > 1:
        surname = parts[-1]

    pairs = [
        (person.full_name, PERSON_TOKEN),
        (person.company, COMPANY_TOKEN),
        (surname, PERSON_TOKEN),
        (person.first_name, PERSON_TOKEN),
    ]
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for term, token in pairs:
        cleaned = str(term or "").strip()
        key = cleaned.lower()
        if len(cleaned) < _MIN_SCRUBBABLE or key in seen:
            continue
        seen.add(key)
        out.append((cleaned, token))
    out.sort(key=lambda item: len(item[0]), reverse=True)
    return out


def scrub_identity(text: str, person: PersonPublic | None) -> str:
    """Replace this person's name and company with tokens, in free text.

    Free-text fields are where identity leaks after the structured fields have
    been handled — a public hook reads "Ana Silva spoke at the EU trade summit"
    just as often as it reads "spoke at the EU trade summit".
    """
    result = str(text or "")
    if person is None or not result:
        return result
    for term, token in _identity_terms(person):
        result = re.sub(rf"\b{re.escape(term)}\b", token, result, flags=re.IGNORECASE)
    return result


def _person_fields(person: PersonPublic, policy: DataPolicy) -> dict[str, Any]:
    """Person fields permitted at each policy level.

    ``strict``       — nothing that identifies the individual.
    ``pseudonymous`` — job title and public hook, with the person and the
                       company replaced by tokens.  Enough to write something
                       specific; not enough to know who it is about.
    ``minimal``      — their real public professional identity, which is what
                       enrichment needs (owner's instruction, tiers A and B).
    ``standard``/``full`` — adds the public hook's source and profile URL.
    """
    built: dict[str, Any] = {}
    # Below `minimal` the person is not supposed to be identifiable, so the
    # free-text fields are scrubbed too. They describe the slot, but nothing
    # stops an operator from typing a name into one.
    anonymise = policy.rank < DataPolicy.MINIMAL.rank

    def _maybe_scrub(value: str) -> str:
        return scrub_identity(value, person) if anonymise else value

    # Present at every level: structural fields that describe the *slot*, not
    # the person. These identify nobody on their own.
    for key, value in (
        ("category", person.category),
        ("route", person.route),
        ("tension", person.tension),
        ("contribution", person.contribution),
    ):
        cleaned = _clean(_maybe_scrub(value), 500)
        if cleaned:
            built[key] = cleaned
    questions = [
        _clean(_maybe_scrub(item), 300)
        for item in person.questions
        if _clean(item, 300)
    ]
    if questions:
        built["questions"] = questions[:3]

    if policy.rank <= DataPolicy.STRICT.rank:
        return built

    if anonymise:
        # pseudonymous: tokens instead of identity. The title is kept because a
        # role names nobody — "Head of Trade" is true of thousands of people —
        # and without it the model cannot pitch at the right level.
        built["person_ref"] = PERSON_TOKEN
        if _clean(person.company, 600):
            built["company_ref"] = COMPANY_TOKEN
        for key, value in (
            ("title", person.title),
            ("public_hook", _maybe_scrub(person.public_hook)),
        ):
            cleaned = _clean(value, 600)
            if cleaned:
                built[key] = cleaned
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

    # Below `minimal` the person must not be identifiable *anywhere* in the
    # payload, not just inside the `recipient` block. Owner-typed free text is
    # the obvious leak: "write to Ana Silva at Acme" carries the identity that
    # the structured fields just removed.
    def _text(value: object, limit: int) -> str:
        cleaned = _clean(value, limit)
        if cleaned and policy.rank < DataPolicy.MINIMAL.rank:
            cleaned = scrub_identity(cleaned, request.person)
        return tokenise_addresses(cleaned)

    instructions = _clean(request.instructions, 6000)
    if instructions:
        built["instructions"] = _text(instructions, 6000)

    if request.person is not None:
        person_fields = _person_fields(request.person, policy)
        if person_fields:
            built["recipient"] = person_fields

    # The owner's public one-liner is the only sender-side content permitted to
    # leave below `full` (§5.2 item 2). It names the owner's offer, not the
    # recipient, so a pseudonymous payload still carries it — without it the
    # model has nothing to pitch.
    positioning = _clean(request.positioning_line, 500)
    if positioning and policy.rank >= DataPolicy.PSEUDONYMOUS.rank:
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
        built["public_context"] = _text(public_text, 20000)

    if request.conversation:
        limit = 20 if policy.rank >= DataPolicy.STANDARD.rank else 6
        built["conversation"] = [
            {
                "role": _clean(turn.get("role"), 20),
                "content": _text(turn.get("content"), 8000),
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
    if policy is DataPolicy.PSEUDONYMOUS:
        return (
            "The job title and public hook, plus your one-line positioning. The "
            "person and company go as PERSON_1 and COMPANY_1, and off_CRM puts "
            "the real names back locally. Nobody is identifiable."
        )
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
