"""Recall over sent mail.

The feature is ordinary: find emails I have already written that are like the
one I am writing now.  The access rules around it are the whole job, so most of
this file tests those rather than the search:

* Received mail is never indexed — refused at two independent layers.
* A quoted reply inside a sent email is cut off before anything is stored.
* The index file on disk contains no name, address or company. Asserted by
  reading the bytes of the database, not by trusting the code that wrote it.
* No model can search it. There is no interface for one to reach.
* Snippets leave only through the broker, as campaign-class material, so the
  existing tier rules keep them away from restricted providers with no
  special-casing for this feature.
"""
from __future__ import annotations

import ast
import io
import json
import tokenize
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    DataClass,
    DataPolicy,
    SentMailIndex,
    TrustTier,
    build_payload,
    build_redactor,
    scan_payload,
    strip_quoted_thread,
    tier_permits_class,
)
from offsetx_apollo_builder.ai.recall import MAX_SNIPPETS_IN_PAYLOAD, Redactor

REPO_ROOT = Path(__file__).resolve().parents[1]
RECALL_SOURCE = REPO_ROOT / "offsetx_apollo_builder" / "ai" / "recall.py"

CONTACTS = [
    {
        "id": "cc-1",
        "full_name": "Anita Rao",
        "first_name": "Anita",
        "last_name": "Rao",
        "company": "Example Exports",
        "email": "anita@example.com",
        "linkedin_url": "https://linkedin.com/in/anitarao",
        "category": "CBAM",
        "route": "importer",
    },
    {
        "id": "cc-2",
        "full_name": "Ravi Shah",
        "first_name": "Ravi",
        "last_name": "Shah",
        "company": "Audit Works",
        "email": "ravi@auditworks.com",
        "category": "MRV",
        "route": "verifier",
    },
]


@pytest.fixture()
def index(tmp_path) -> SentMailIndex:
    return SentMailIndex(tmp_path / "recall.db")


@pytest.fixture()
def redactor() -> Redactor:
    return build_redactor(
        CONTACTS, owner_addresses=["kunal@offsetx.com"], owner_domains=["offsetx.com"]
    )


def _sent(body: str, *, subject: str = "Supplier evidence", message_id: str = "m1") -> dict:
    return {
        "id": message_id,
        "direction": "outbound",
        "campaign_contact_id": "cc-1",
        "subject": subject,
        "body": body,
        "stage": "initial",
        "template_id": "initial-a",
        "variant_id": "A",
        "sent_at": "2026-07-01T10:00:00+00:00",
    }


# ── rule 1: received mail is never indexed ──────────────────────────────────


def test_received_mail_is_refused(index, redactor):
    """Not redacted and stored — refused. The safe way to hold mailbox content
    is not to hold it."""
    reply = {
        "id": "r1",
        "direction": "inbound",
        "subject": "Re: Supplier evidence",
        "body": "Sure, call me on 07700 900999.",
    }
    assert index.index_message(reply, redactor=redactor) is None
    assert index.stats()["indexed"] == 0


def test_the_store_query_cannot_return_received_mail(tmp_path):
    """The second layer: the SQL itself filters to outbound, so a caller cannot
    reach inbound mail by passing the wrong argument."""
    import inspect

    from offsetx_apollo_builder.outreach.store import OutreachStore

    source = inspect.getsource(OutreachStore.sent_messages)
    assert "direction = 'outbound'" in source
    # No parameter exists that could switch the direction.
    parameters = set(inspect.signature(OutreachStore.sent_messages).parameters)
    assert parameters == {"self", "campaign_id", "limit"}
    # Behaviour against a database that really holds a reply is proved by
    # test_rebuild_indexes_sent_mail_and_ignores_the_reply below.


def test_a_quoted_reply_is_cut_off_before_indexing(index, redactor):
    """A follow-up quotes the reply underneath it. That block is *their* mail
    sitting inside *your* mail, and it must not survive into the index."""
    body = (
        "Hi Anita, following up on the supplier brief.\n\n"
        "On Tue, 5 Jul 2026, Anita Rao <anita@example.com> wrote:\n"
        "> No thanks. My direct line is 07700 900999 and my home address is "
        "12 Rose Lane.\n"
    )
    record = index.index_message(_sent(body), redactor=redactor)
    assert record is not None
    assert "900999" not in record.body
    assert "Rose Lane" not in record.body
    assert "wrote:" not in record.body
    assert "following up" in record.body


@pytest.mark.parametrize(
    "marker",
    [
        "On Mon, 3 Mar 2025, Someone wrote:",
        "-----Original Message-----",
        "--- Forwarded message ---",
        "> quoted line",
    ],
)
def test_every_quote_marker_cuts(marker):
    kept = strip_quoted_thread(f"My own words.\n{marker}\nTheir private words.")
    assert "My own words." in kept
    assert "Their private words" not in kept


# ── rule 2: the index on disk holds no identity ─────────────────────────────


def test_the_database_file_contains_no_personal_data(tmp_path, redactor):
    """The strongest statement this feature can make, and it reads the actual
    bytes on disk rather than trusting the code that wrote them.

    Most retrieval systems store the raw text and redact on the way out, which
    makes the index the most dangerous file in the product. Redacting before the
    write means a stolen index file is worth nothing.
    """
    index = SentMailIndex(tmp_path / "recall.db")
    body = (
        "Hi Anita, I saw Example Exports published a brief. I mentioned it to "
        "Ravi Shah at Audit Works. Reply to anita@example.com or "
        "kunal@offsetx.com, or call +44 7700 900123. Profile: "
        "https://linkedin.com/in/anitarao"
    )
    assert index.index_message(_sent(body), redactor=redactor) is not None
    index.close()

    raw = (tmp_path / "recall.db").read_bytes()
    extra = list((tmp_path).glob("recall.db-*"))  # WAL and shm, if present
    for path in extra:
        raw += path.read_bytes()
    blob = raw.decode("utf-8", errors="ignore").lower()

    for secret in (
        "anita",
        "rao",
        "ravi",
        "shah",
        "example exports",
        "audit works",
        "anita@example.com",
        "kunal@offsetx.com",
        "linkedin.com/in/anitarao",
        "7700 900123",
    ):
        assert secret not in blob, f"{secret!r} survived into the index file"

    # The useful part did survive — this is a redaction, not a deletion.
    assert "brief" in blob


def test_a_name_from_another_contact_is_also_removed(index, redactor):
    """An email to one person routinely names another. Redacting only the
    recipient would leave everybody else in the index."""
    record = index.index_message(
        _sent("Anita, Ravi Shah at Audit Works said the same."), redactor=redactor
    )
    assert record is not None
    assert "Ravi" not in record.body and "Audit Works" not in record.body


def test_the_owners_own_address_is_removed_too(index):
    redactor = build_redactor(CONTACTS, owner_addresses=["kunal@offsetx.com"])
    record = index.index_message(_sent("Reply to kunal@offsetx.com"), redactor=redactor)
    assert record is not None
    assert "kunal" not in record.body.lower()


def test_an_address_no_contact_list_knows_about_is_still_caught(index, redactor):
    """The pattern pass exists for exactly this: something typed by hand that no
    contact record could have told us about."""
    record = index.index_message(
        _sent("Copy in procurement@totally-unknown-company.example next time."),
        redactor=redactor,
    )
    assert record is not None
    assert "@" not in record.body


def test_a_date_is_not_mistaken_for_a_phone_number(index, redactor):
    """Over-redaction is the safe side, but blanking every date would make the
    snippets useless, and a date identifies nobody."""
    record = index.index_message(_sent("The deadline is 2026-07-30."), redactor=redactor)
    assert record is not None and "2026-07-30" in record.body


def test_longest_name_wins_so_no_fragment_is_left_behind():
    redactor = build_redactor([{"company": "Example Exports", "full_name": "Example"}])
    assert "Exports" not in redactor("I work with Example Exports on this.")


# ── rule 3: no model can search this ────────────────────────────────────────


def _code_only(source: str) -> str:
    """Source with comments and docstrings removed.

    The prose describes the interfaces this module deliberately lacks, so a
    plain substring search would flag the sentence promising their absence.
    """
    docstrings = {
        (node.body[0].value.lineno, node.body[0].value.col_offset)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    kept = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and token.start in docstrings:
            continue
        kept.append(token.string)
    return "\n".join(kept)


def test_no_model_can_search_this_index():
    """A model that can *ask* for a document has access to all of them.

    off_CRM chooses the search, reads the result and pushes a payload. There is
    no path in the other direction, and this asserts there is no code for one.
    """
    code = _code_only(RECALL_SOURCE.read_text(encoding="utf-8"))
    for marker in ("tool_choice", '"tools"', "function_call", "mcp", "generate("):
        assert marker not in code, f"recall must not expose {marker} to a model"

    tree = ast.parse(RECALL_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.endswith("providers"), "recall must not import a provider"
            assert "broker" not in node.module, "recall must not reach the broker itself"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in {"requests", "httpx", "urllib"}, (
                    "search runs locally; there is no network call here"
                )


def test_search_uses_no_embeddings_and_no_api_key():
    """Embedding every sent email through an API would post the entire archive
    to a provider. Local full-text search costs nothing and sends nothing.

    Checked against imports and calls rather than the word, so the module stays
    free to *report* ``embeddings_used: False`` to the UI.
    """
    tree = ast.parse(RECALL_SOURCE.read_text(encoding="utf-8"))
    banned = {
        "openai",
        "anthropic",
        "sentence_transformers",
        "transformers",
        "torch",
        "faiss",
        "chromadb",
        "requests",
        "httpx",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned, node.module
        # No `something.embeddings.create(...)` style call anywhere.
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"embeddings", "embed", "encode"}, node.attr

    # And no credential ever reaches this module.
    code = _code_only(RECALL_SOURCE.read_text(encoding="utf-8")).lower()
    for marker in ("api_key", "base_url", "authorization", "bearer"):
        assert marker not in code


# ── rule 4: snippets leave only through the gate ────────────────────────────


def test_recalled_snippets_are_campaign_class(index, redactor):
    """Calling redacted sent mail 'public' would smuggle it past the rule that
    keeps campaign material away from lower-trust providers. It is the owner's
    own business writing, so it is campaign material."""
    index.index_message(_sent("Supplier evidence handoff for the brief."), redactor=redactor)
    request = index.recall_request(index.search("supplier"))
    assert request.data_class is DataClass.CAMPAIGN
    assert request.person is None
    # Not smuggled through the field that reaches every provider.
    assert request.public_text == ""
    assert request.unrestricted == {}


def test_a_restricted_provider_never_receives_recalled_mail():
    """Falls out of the existing tier table — no special case was written for
    this feature, which is why it cannot be forgotten later."""
    assert tier_permits_class(TrustTier.A, DataClass.CAMPAIGN) is True
    assert tier_permits_class(TrustTier.B, DataClass.CAMPAIGN) is True
    assert tier_permits_class(TrustTier.C, DataClass.CAMPAIGN) is False
    assert tier_permits_class(TrustTier.D, DataClass.CAMPAIGN) is False


def test_snippets_need_a_standard_policy_to_leave(index, redactor):
    """The second, independent barrier: snippets travel as prior drafts, which
    a minimal policy does not carry at all."""
    index.index_message(_sent("Supplier evidence handoff."), redactor=redactor)
    request = index.recall_request(index.search("supplier"))

    minimal = build_payload(request, DataPolicy.MINIMAL)
    assert "prior_drafts" not in minimal

    standard = build_payload(request, DataPolicy.STANDARD)
    assert standard["prior_drafts"][0]["body"]


def test_a_recalled_payload_passes_the_scanner(index, redactor):
    """Belt and braces: redaction happens at index time, and the payload is
    still scanned on the way out. If redaction ever regressed, this blocks."""
    body = (
        "Hi Anita at Example Exports, reply to anita@example.com or call "
        "+44 7700 900123 about the supplier brief."
    )
    index.index_message(_sent(body), redactor=redactor)
    payload = build_payload(index.recall_request(index.search("supplier")), DataPolicy.STANDARD)
    report = scan_payload(payload, policy=DataPolicy.STANDARD)
    assert report.clean, [finding.detail for finding in report.findings]


def test_the_payload_cap_matches_what_actually_leaves(index, redactor):
    """A caller asking for six examples must not be quietly given three."""
    for number in range(6):
        index.index_message(
            _sent(f"Supplier brief number {number}.", message_id=f"m{number}"),
            redactor=redactor,
        )
    found = index.search("supplier", limit=6)
    assert len(found) == 6
    request = index.recall_request(found)
    assert len(request.prior_drafts) == MAX_SNIPPETS_IN_PAYLOAD
    payload = build_payload(request, DataPolicy.STANDARD)
    assert len(payload["prior_drafts"]) == len(request.prior_drafts)


# ── the search itself ───────────────────────────────────────────────────────


def test_search_finds_past_emails(index, redactor):
    index.index_message(_sent("Customs paperwork for the shipment.", message_id="m1"), redactor=redactor)
    index.index_message(_sent("Emissions reporting deadline.", message_id="m2"), redactor=redactor)
    found = index.search("customs")
    assert [item.message_id for item in found] == ["m1"]


def test_search_can_be_limited_to_emails_that_worked(index, redactor):
    index.index_message(_sent("Customs paperwork one.", message_id="m1"), redactor=redactor)
    index.index_message(_sent("Customs paperwork two.", message_id="m2"), redactor=redactor)
    index.mark_replied("m2")
    assert [item.message_id for item in index.search("customs", replied_only=True)] == ["m2"]
    assert index.stats()["replied"] == 1


def test_search_words_typed_by_a_person_cannot_break_the_query(index, redactor):
    """FTS5 has its own operator syntax. A person typing one must get a search,
    not a crash."""
    index.index_message(_sent("Customs paperwork."), redactor=redactor)
    for query in ('customs OR "', "customs AND NEAR(", "*", "^customs", ""):
        assert isinstance(index.search(query), list)


def test_reindexing_the_same_message_does_not_duplicate_it(index, redactor):
    index.index_message(_sent("Customs paperwork."), redactor=redactor)
    index.index_message(_sent("Customs paperwork."), redactor=redactor)
    assert index.stats()["indexed"] == 1
    assert len(index.search("customs")) == 1


def test_a_reply_flag_survives_reindexing(index, redactor):
    index.index_message(_sent("Customs paperwork."), redactor=redactor)
    index.mark_replied("m1")
    index.index_message(_sent("Customs paperwork, edited."), redactor=redactor)
    assert index.stats()["replied"] == 1


# ── deletion ────────────────────────────────────────────────────────────────


def test_a_person_can_be_forgotten(index, redactor):
    """"We already removed your name" is not an answer to a deletion request."""
    index.index_message(_sent("Customs paperwork.", message_id="m1"), redactor=redactor)
    assert index.forget_contact("cc-1") == 1
    assert index.stats()["indexed"] == 0
    assert index.search("customs") == []


def test_clearing_the_index_empties_the_search_too(index, redactor):
    index.index_message(_sent("Customs paperwork."), redactor=redactor)
    assert index.clear() == 1
    assert index.search("customs") == []


# ── end to end, against the real CRM ────────────────────────────────────────


def test_the_live_send_path_indexes_and_the_reply_only_sets_a_flag(tmp_path):
    """Wired into sending, not just available to a rebuild.

    After one send and one reply the index must hold exactly one row, that row
    must be marked as having worked, and nothing the recipient wrote may appear
    in it.
    """
    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider

    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
        "Published a supplier emissions brief,https://example.com/anita,"
        "Supplier evidence handoff\n",
        encoding="utf-8",
    )
    index = SentMailIndex(tmp_path / "recall.db")
    engine = OutreachEngine(tmp_path / "outreach.db", mail_archive=index)
    campaign_id = engine.create_campaign(name="Pilot")
    engine.import_contacts(campaign_id, contacts)
    engine.generate_drafts(campaign_id)
    engine.approve_drafts(campaign_id, stages=["initial"])

    mail = LocalOutboxProvider(tmp_path / "mail")
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    engine.run_due(campaign_id, mail_provider=mail, own_email="kunal@offsetx.com", now=now)

    assert index.stats()["indexed"] == 1, "sending must fill the index by itself"
    stored = index.recent()[0]
    assert "Anita" not in stored.body and "anita@example.com" not in stored.body
    assert "Example Exports" not in stored.body

    contact = next(
        item for item in engine.store.campaign_contacts(campaign_id) if item["sent_count"]
    )
    outgoing = engine.store.last_outgoing(contact["id"])
    (tmp_path / "mail" / "inbox" / "reply.json").write_text(
        json.dumps(
            {
                "id": "reply-1",
                "thread_id": outgoing["thread_id"],
                "from": contact["email"],
                "subject": "Re: evidence",
                "body": "Interested. My private number is 07700 900999.",
                "received_at": (now + timedelta(hours=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    engine.sync_replies(
        campaign_id, mail_provider=mail, own_email="kunal@offsetx.com", now=now + timedelta(hours=2)
    )

    stats = index.stats()
    assert stats["indexed"] == 1, "a reply must not add a row"
    assert stats["replied"] == 1, "it must mark the sent email as one that worked"
    everything = " ".join(item.body + item.subject for item in index.recent())
    assert "900999" not in everything and "Interested" not in everything
    engine.close()


def test_a_broken_archive_never_costs_a_send(tmp_path):
    """The email has already left. Losing a search entry must not turn a
    successful send into a reported failure."""
    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider

    class BrokenArchive:
        def archive_send(self, message, **_):
            raise RuntimeError("disk on fire")

        def mark_replied(self, message_id):
            raise RuntimeError("disk on fire")

    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
        "Published a supplier emissions brief,https://example.com/anita,"
        "Supplier evidence handoff\n",
        encoding="utf-8",
    )
    engine = OutreachEngine(tmp_path / "outreach.db", mail_archive=BrokenArchive())
    campaign_id = engine.create_campaign(name="Pilot")
    engine.import_contacts(campaign_id, contacts)
    engine.generate_drafts(campaign_id)
    engine.approve_drafts(campaign_id, stages=["initial"])
    result = engine.run_due(
        campaign_id,
        mail_provider=LocalOutboxProvider(tmp_path / "mail"),
        own_email="kunal@offsetx.com",
        now=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    assert result["sent_count"] == 1 and result["failed"] == []
    engine.close()


def test_rebuild_indexes_sent_mail_and_ignores_the_reply(tmp_path):
    """Drives a real send and a real reply through the engine, then rebuilds.

    The sent email must be indexed. The reply must not be, even though it sits
    in the same table two rows away.
    """
    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider

    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
        "Published a supplier emissions brief,https://example.com/anita,"
        "Supplier evidence handoff\n",
        encoding="utf-8",
    )
    engine = OutreachEngine(tmp_path / "outreach.db")
    campaign_id = engine.create_campaign(name="Pilot")
    engine.import_contacts(campaign_id, contacts)
    engine.generate_drafts(campaign_id)
    engine.approve_drafts(campaign_id, stages=["initial"])

    mail = LocalOutboxProvider(tmp_path / "mail")
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    engine.run_due(campaign_id, mail_provider=mail, own_email="kunal@offsetx.com", now=now)

    contact = next(
        item for item in engine.store.campaign_contacts(campaign_id) if item["sent_count"]
    )
    outgoing = engine.store.last_outgoing(contact["id"])
    (tmp_path / "mail" / "inbox" / "reply.json").write_text(
        json.dumps(
            {
                "id": "reply-1",
                "thread_id": outgoing["thread_id"],
                "from": contact["email"],
                "subject": "Re: evidence",
                "body": "My private number is 07700 900999.",
                "received_at": (now + timedelta(hours=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    engine.sync_replies(
        campaign_id, mail_provider=mail, own_email="kunal@offsetx.com", now=now + timedelta(hours=2)
    )

    index = SentMailIndex(tmp_path / "recall.db")
    result = index.rebuild(engine.store)
    assert result["indexed"] == 1, "exactly the one sent email"

    # The reply is in the messages table but must not be in the index anywhere.
    assert index.search("private") == []
    assert index.search("900999") == []
    everything = " ".join(item.body + item.subject for item in index.recent())
    assert "900999" not in everything
    assert "Anita" not in everything and "anita@example.com" not in everything
    engine.close()
