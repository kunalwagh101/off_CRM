"""Recall over the owner's own sent mail — retrieval without a leak.

A normal RAG stack leaks in four places, and each one is closed here by
construction rather than by care:

1. **Embedding the documents.**  Calling an embedding API means posting every
   email you ever sent to a provider.  So there are no embeddings.  Search is
   local full-text search (SQLite FTS5): no key, no network, no per-document
   cost, and it works offline.
2. **The index itself.**  Most stacks store the raw text and redact on the way
   out, which makes the index the most dangerous file in the product.  Here the
   text is **redacted before it is stored**, so the index has nothing to leak.
3. **Retrieval as a model tool.**  A model that can *ask* for a document has
   access to all of them.  There is no query interface here that a model can
   reach.  off_CRM chooses the search, reads the result, and pushes a payload.
4. **The retrieved text going straight into the prompt.**  Snippets leave only
   as an :class:`~offsetx_apollo_builder.ai.payload.EgressRequest`, through the
   same broker, policy, scanner and log as everything else.

Two further rules specific to mail:

* **Sent mail only.**  Received mail is mailbox content and is never indexed —
  not redacted and stored, simply never taken.  :meth:`SentMailIndex.index_message`
  refuses an inbound row.
* **Quoted threads are cut off first.**  A follow-up often quotes the reply
  underneath it.  That quoted part is *their* mail sitting inside *your* mail,
  so it is removed before anything is stored.

The class of the material is :attr:`DataClass.CAMPAIGN`: a redacted sent email
is the owner's own business writing.  It is not public, and calling it public
would smuggle it past the restriction that keeps campaign material away from
lower-trust providers.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .payload import EgressRequest
from .tiers import DataClass

#: How many past emails may ride along in one payload.  Matches the cap already
#: applied by ``build_payload`` to ``prior_drafts`` — kept equal on purpose so a
#: caller is never quietly given fewer examples than it asked for.
MAX_SNIPPETS_IN_PAYLOAD = 3

#: Stored body length.  Outreach mail is short; this is a ceiling, not a target.
MAX_BODY_CHARS = 4000

#: A first name shorter than this is skipped by the redactor.  "Jo" as a word
#: boundary match would blank half the dictionary for no safety gain, because a
#: two-letter token identifies nobody on its own.
MIN_NAME_LENGTH = 3

#: Where a quoted reply starts.  Everything from the first hit is *their* mail
#: and is dropped before indexing.
_QUOTE_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*on .{5,120}\bwrote:\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"-{2,}\s*original message\s*-{2,}", re.IGNORECASE),
    re.compile(r"-{2,}\s*forwarded message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^\s*from:\s.+$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*sent from my \w+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*>", re.MULTILINE),
)

#: The net that catches what the known-value pass could not know about: an
#: address, a number or a link typed into the body by hand.
#:
#: Note the lookaheads end at ``\w`` and not at ``[\w.]``.  Including the full
#: stop meant a number that ended a sentence — which is most of them — never
#: matched at all.
_GENERIC_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[email]"),
    (re.compile(r"\bhttps?://\S+", re.IGNORECASE), "[link]"),
    (re.compile(r"\bwww\.[^\s,;]+", re.IGNORECASE), "[link]"),
    # Long bare digit runs — order numbers, reference ids, account numbers.
    (re.compile(r"(?<![\w.])\d{6,}(?!\w)"), "[number]"),
)

#: Phone-shaped runs of digits and separators.  Checked for digit count rather
#: than blanked on sight, so an ISO date does not read as a phone number and
#: vanish — dates carry real meaning in outreach mail.
_PHONE_RE = re.compile(r"(?<![\w.])\+?\d[\d\s().-]{6,}\d(?!\w)")
_MIN_PHONE_DIGITS = 9


def _redact_phones(text: str) -> str:
    def swap(match: re.Match[str]) -> str:
        digits = sum(character.isdigit() for character in match.group(0))
        return "[phone]" if digits >= _MIN_PHONE_DIGITS else match.group(0)

    return _PHONE_RE.sub(swap, text)

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: object) -> str:
    return str(value or "").strip()


def strip_quoted_thread(body: str) -> str:
    """Cut a message at the point where it starts quoting somebody else.

    A follow-up email is *sent* mail, but the block underneath it is usually the
    recipient's reply — received mail, which may never be indexed or sent
    anywhere.  Cutting at the earliest marker is the conservative choice: it can
    lose a little of the owner's own text, and that costs nothing.
    """
    text = str(body or "")
    cut = len(text)
    for pattern in _QUOTE_MARKERS:
        match = pattern.search(text)
        if match is not None:
            cut = min(cut, match.start())
    return text[:cut].strip()


@dataclass(frozen=True, slots=True)
class Identity:
    """The strings that name one person or company, for the redactor to remove."""

    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    email: str = ""
    linkedin_url: str = ""

    @classmethod
    def from_contact(cls, contact: dict[str, Any]) -> "Identity":
        return cls(
            full_name=_clean(contact.get("full_name")),
            first_name=_clean(contact.get("first_name")),
            last_name=_clean(contact.get("last_name")),
            company=_clean(contact.get("company")),
            email=_clean(contact.get("email")),
            linkedin_url=_clean(contact.get("linkedin_url")),
        )


class Redactor:
    """Removes identities from text before it is stored.

    Two passes, in this order:

    *Known values first.*  off_CRM knows exactly who its contacts are, so it can
    delete their names precisely instead of guessing at them the way a general
    PII detector has to.  That is far stronger than pattern matching, and it is
    why the vocabulary covers **every** contact rather than only this message's
    recipient — an email to one person routinely mentions another.

    *Patterns second*, for what no contact list could know: an address or number
    typed straight into the body.

    Where the two disagree the safer answer wins.  A common first name such as
    "Mark" or "Rose" is removed even though it costs a legitimate word now and
    then, because an over-redacted snippet is merely less useful, while an
    under-redacted one is a leak.
    """

    def __init__(
        self,
        identities: Iterable[Identity] = (),
        *,
        owner_addresses: Iterable[str] = (),
        owner_domains: Iterable[str] = (),
    ) -> None:
        terms: dict[str, str] = {}

        def add(value: str, placeholder: str, *, minimum: int = 2) -> None:
            text = _clean(value)
            if len(text) >= minimum:
                terms.setdefault(text.lower(), placeholder)

        for identity in identities:
            add(identity.email, "[email]")
            add(identity.linkedin_url, "[link]")
            add(identity.full_name, "[name]", minimum=MIN_NAME_LENGTH)
            add(identity.first_name, "[name]", minimum=MIN_NAME_LENGTH)
            add(identity.last_name, "[name]", minimum=MIN_NAME_LENGTH)
            add(identity.company, "[company]", minimum=MIN_NAME_LENGTH)
        for address in owner_addresses:
            add(address, "[email]")
        for domain in owner_domains:
            add(domain, "[domain]")

        self._placeholders = terms
        # Longest first, so "Example Exports Ltd" is replaced whole rather than
        # leaving "Exports Ltd" behind after "Example" matched.
        ordered = sorted(terms, key=len, reverse=True)
        self._pattern = (
            re.compile(
                r"(?<![\w@.])(?:%s)(?![\w])" % "|".join(re.escape(term) for term in ordered),
                re.IGNORECASE,
            )
            if ordered
            else None
        )

    @property
    def term_count(self) -> int:
        return len(self._placeholders)

    def __call__(self, text: str) -> str:
        result = str(text or "")
        if self._pattern is not None:
            result = self._pattern.sub(
                lambda match: self._placeholders.get(match.group(0).lower(), "[redacted]"),
                result,
            )
        result = _redact_phones(result)
        for pattern, placeholder in _GENERIC_PATTERNS:
            result = pattern.sub(placeholder, result)
        result = _WHITESPACE_RE.sub(" ", result)
        return _BLANK_LINES_RE.sub("\n\n", result).strip()


def build_redactor(
    contacts: Iterable[dict[str, Any]],
    *,
    owner_addresses: Iterable[str] = (),
    owner_domains: Iterable[str] = (),
) -> Redactor:
    """Vocabulary from a whole contact list, not one contact.

    An email to Anita often names Ravi.  Redacting only the recipient would
    leave Ravi in the index, so the vocabulary covers everybody off_CRM knows.
    """
    return Redactor(
        (Identity.from_contact(contact) for contact in contacts),
        owner_addresses=owner_addresses,
        owner_domains=owner_domains,
    )


@dataclass(slots=True)
class Recalled:
    """One past email, already redacted, ready to be shown or sent."""

    message_id: str
    subject: str
    body: str
    template_id: str = ""
    variant_id: str = ""
    stage: str = ""
    category: str = ""
    got_reply: bool = False
    sent_at: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "body": self.body,
            "template_id": self.template_id,
            "variant_id": self.variant_id,
            "stage": self.stage,
            "category": self.category,
            "got_reply": self.got_reply,
            "sent_at": self.sent_at,
            "score": self.score,
        }


class SentMailIndex:
    """Local, redacted, searchable memory of what the owner has already sent.

    Note what this class does *not* have: a network call, a provider import, an
    embedding model, or any method a model could be handed as a tool.  It reads
    from off_CRM and returns Python objects.  Everything that leaves does so
    through the broker, as an :class:`EgressRequest` built by
    :meth:`recall_request`.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._local = threading.local()
        self._redactor_cache: dict[str, tuple[int, Redactor]] = {}
        self._initialise()

    # ── storage ────────────────────────────────────────────────────────────

    @property
    def connection(self) -> sqlite3.Connection:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            self._local.connection = connection
        return connection

    def _initialise(self) -> None:
        with self._lock:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sent_mail (
                    message_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL DEFAULT 'local',
                    campaign_id TEXT NOT NULL DEFAULT '',
                    campaign_contact_id TEXT NOT NULL DEFAULT '',
                    template_id TEXT NOT NULL DEFAULT '',
                    variant_id TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    route TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL DEFAULT '',
                    body TEXT NOT NULL DEFAULT '',
                    got_reply INTEGER NOT NULL DEFAULT 0,
                    sent_at TEXT NOT NULL DEFAULT '',
                    indexed_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS sent_mail_workspace
                    ON sent_mail(workspace_id, sent_at DESC);
                CREATE INDEX IF NOT EXISTS sent_mail_contact
                    ON sent_mail(campaign_contact_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS sent_mail_fts USING fts5(
                    subject,
                    body,
                    message_id UNINDEXED,
                    workspace_id UNINDEXED,
                    tokenize='porter unicode61'
                );
                """
            )

    def close(self) -> None:
        connection = getattr(self._local, "connection", None)
        if connection is not None:
            connection.close()
            self._local.connection = None

    # ── indexing ───────────────────────────────────────────────────────────

    def index_message(
        self,
        message: dict[str, Any],
        *,
        redactor: Redactor,
        workspace_id: str = "local",
        campaign_id: str = "",
        category: str = "",
        route: str = "",
    ) -> Recalled | None:
        """Store one **sent** message, redacted.

        Returns ``None`` when the row is not indexable.  An inbound message is
        refused outright rather than redacted and kept: received mail is mailbox
        content, and the safe way to hold mailbox content is not to.
        """
        if _clean(message.get("direction")).lower() != "outbound":
            return None
        message_id = _clean(message.get("id"))
        if not message_id:
            return None

        body = strip_quoted_thread(_clean(message.get("body")))
        subject = redactor(_clean(message.get("subject")))
        body = redactor(body)[:MAX_BODY_CHARS]
        if not subject and not body:
            return None

        record = Recalled(
            message_id=message_id,
            subject=subject,
            body=body,
            template_id=_clean(message.get("template_id")) or _clean(message.get("stage")),
            variant_id=_clean(message.get("variant_id")),
            stage=_clean(message.get("stage")),
            category=_clean(category),
            got_reply=False,
            sent_at=_clean(message.get("sent_at")),
        )
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM sent_mail_fts WHERE message_id = ?", (message_id,)
            )
            self.connection.execute(
                """
                INSERT INTO sent_mail (
                    message_id, workspace_id, campaign_id, campaign_contact_id,
                    template_id, variant_id, stage, category, route,
                    subject, body, got_reply, sent_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          COALESCE((SELECT got_reply FROM sent_mail WHERE message_id = ?), 0),
                          ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    subject = excluded.subject,
                    body = excluded.body,
                    indexed_at = excluded.indexed_at
                """,
                (
                    message_id,
                    workspace_id,
                    _clean(campaign_id),
                    _clean(message.get("campaign_contact_id")),
                    record.template_id,
                    record.variant_id,
                    record.stage,
                    record.category,
                    _clean(route),
                    subject,
                    body,
                    message_id,
                    record.sent_at,
                    _now(),
                ),
            )
            self.connection.execute(
                "INSERT INTO sent_mail_fts (subject, body, message_id, workspace_id)"
                " VALUES (?, ?, ?, ?)",
                (subject, body, message_id, workspace_id),
            )
        return record

    def archive_send(
        self,
        message: dict[str, Any],
        *,
        contacts: Sequence[dict[str, Any]],
        workspace_id: str = "local",
        campaign_id: str = "",
        owner_addresses: Iterable[str] = (),
    ) -> Recalled | None:
        """Index one message the CRM has just sent.

        The redaction vocabulary is built here rather than by the caller, so the
        outreach side never has to import this package — it only has to hand
        over the message and the contact list.  That keeps the AI module liftable
        into its own repository.

        The compiled vocabulary is cached against a fingerprint of the contact
        list, because recompiling a few thousand names for every single send
        would make the archive the slowest part of sending.
        """
        redactor = self._redactor_for(campaign_id, contacts, owner_addresses)
        contact = next(
            (
                item
                for item in contacts
                if str(item.get("id", "")) == _clean(message.get("campaign_contact_id"))
            ),
            {},
        )
        return self.index_message(
            message,
            redactor=redactor,
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            category=_clean(contact.get("category")),
            route=_clean(contact.get("route")),
        )

    def _redactor_for(
        self,
        campaign_id: str,
        contacts: Sequence[dict[str, Any]],
        owner_addresses: Iterable[str],
    ) -> Redactor:
        addresses = tuple(owner_addresses)
        fingerprint = hash(
            (
                len(contacts),
                addresses,
                tuple(
                    sorted(
                        f"{item.get('full_name', '')}|{item.get('company', '')}"
                        f"|{item.get('email', '')}"
                        for item in contacts
                    )
                ),
            )
        )
        cached = self._redactor_cache.get(campaign_id)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]
        redactor = build_redactor(contacts, owner_addresses=addresses)
        self._redactor_cache[campaign_id] = (fingerprint, redactor)
        return redactor

    def mark_replied(self, message_id: str) -> None:
        """Record that this email earned a reply.

        Only the fact, never the reply.  It makes "show me emails like this that
        actually worked" possible, which is the search worth having.
        """
        with self._lock, self.connection:
            self.connection.execute(
                "UPDATE sent_mail SET got_reply = 1 WHERE message_id = ?", (str(message_id),)
            )

    def rebuild(self, store: Any, *, workspace_id: str = "local") -> dict[str, int]:
        """Index every sent message already in the CRM.

        Reads the contact list once to build the redaction vocabulary, so a name
        belonging to one contact is removed from every other contact's email too.
        """
        campaigns, _ = store.list_campaigns(limit=10000)
        indexed = 0
        skipped = 0
        for campaign in campaigns:
            campaign_id = str(campaign.get("id", ""))
            contacts = [dict(row) for row in store.campaign_contacts(campaign_id)]
            redactor = build_redactor(contacts)
            for message in store.sent_messages(campaign_id):
                result = self.index_message(
                    message,
                    redactor=redactor,
                    workspace_id=workspace_id,
                    campaign_id=campaign_id,
                    category=_clean(message.get("contact_category")),
                    route=_clean(message.get("contact_route")),
                )
                if result is None:
                    skipped += 1
                else:
                    indexed += 1
        return {"indexed": indexed, "skipped": skipped, "campaigns": len(campaigns)}

    # ── search (local only — no model can reach this) ───────────────────────

    @staticmethod
    def _match_expression(query: str) -> str:
        """Turn owner-typed words into a safe FTS5 expression.

        Every word is quoted, so FTS operators a person happened to type are
        treated as text instead of changing the meaning of the search.
        """
        words = re.findall(r"[\w']+", str(query or ""), flags=re.UNICODE)
        return " OR ".join(f'"{word}"' for word in words if len(word) > 1)

    def search(
        self,
        query: str,
        *,
        workspace_id: str = "local",
        limit: int = 5,
        replied_only: bool = False,
    ) -> list[Recalled]:
        """Find past emails. Runs entirely on this machine.

        Nothing here contacts a provider, and the rows returned are the redacted
        ones — there is no un-redacted copy to return.
        """
        expression = self._match_expression(query)
        if not expression:
            return []
        rows = self.connection.execute(
            """
            SELECT s.*, bm25(sent_mail_fts) AS rank
            FROM sent_mail_fts
            JOIN sent_mail s ON s.message_id = sent_mail_fts.message_id
            WHERE sent_mail_fts MATCH ?
              AND sent_mail_fts.workspace_id = ?
              AND (? = 0 OR s.got_reply = 1)
            ORDER BY rank
            LIMIT ?
            """,
            (expression, workspace_id, int(bool(replied_only)), max(1, int(limit))),
        ).fetchall()
        return [self._to_recalled(row) for row in rows]

    def recent(self, *, workspace_id: str = "local", limit: int = 10) -> list[Recalled]:
        rows = self.connection.execute(
            "SELECT *, 0.0 AS rank FROM sent_mail WHERE workspace_id = ?"
            " ORDER BY sent_at DESC LIMIT ?",
            (workspace_id, max(1, int(limit))),
        ).fetchall()
        return [self._to_recalled(row) for row in rows]

    @staticmethod
    def _to_recalled(row: sqlite3.Row) -> Recalled:
        return Recalled(
            message_id=str(row["message_id"]),
            subject=str(row["subject"]),
            body=str(row["body"]),
            template_id=str(row["template_id"]),
            variant_id=str(row["variant_id"]),
            stage=str(row["stage"]),
            category=str(row["category"]),
            got_reply=bool(row["got_reply"]),
            sent_at=str(row["sent_at"]),
            score=float(row["rank"] or 0.0),
        )

    # ── the one way out ────────────────────────────────────────────────────

    def recall_request(
        self,
        snippets: Sequence[Recalled],
        *,
        task_type: str = "write_email",
        instructions: str = "",
    ) -> EgressRequest:
        """Package recalled emails for the broker.

        The class is ``CAMPAIGN``, which is the honest label: this is the
        owner's own business writing with the people taken out.  It is not
        public, so it does not reach a provider that may only receive public
        material — and because the snippets travel as ``prior_drafts`` they need
        a ``standard`` policy as well.  Two independent barriers, neither of
        them special-cased for this feature.
        """
        return EgressRequest(
            task_type=task_type,
            data_class=DataClass.CAMPAIGN,
            instructions=instructions,
            prior_drafts=[
                {"subject": item.subject, "body": item.body}
                for item in snippets[:MAX_SNIPPETS_IN_PAYLOAD]
            ],
            task_tags=("recall",),
        )

    # ── deletion ───────────────────────────────────────────────────────────

    def forget_message(self, message_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM sent_mail WHERE message_id = ?", (str(message_id),)
            )
            self.connection.execute(
                "DELETE FROM sent_mail_fts WHERE message_id = ?", (str(message_id),)
            )

    def forget_contact(self, campaign_contact_id: str) -> int:
        """Remove every indexed email to one person.

        Needed even though the index is redacted: a person may ask to be
        forgotten, and "we already took your name out" is not an answer to that.
        """
        with self._lock, self.connection:
            rows = self.connection.execute(
                "SELECT message_id FROM sent_mail WHERE campaign_contact_id = ?",
                (str(campaign_contact_id),),
            ).fetchall()
            for row in rows:
                self.connection.execute(
                    "DELETE FROM sent_mail_fts WHERE message_id = ?", (row["message_id"],)
                )
            self.connection.execute(
                "DELETE FROM sent_mail WHERE campaign_contact_id = ?",
                (str(campaign_contact_id),),
            )
        return len(rows)

    def clear(self, *, workspace_id: str = "local") -> int:
        with self._lock, self.connection:
            rows = self.connection.execute(
                "SELECT message_id FROM sent_mail WHERE workspace_id = ?", (workspace_id,)
            ).fetchall()
            for row in rows:
                self.connection.execute(
                    "DELETE FROM sent_mail_fts WHERE message_id = ?", (row["message_id"],)
                )
            self.connection.execute("DELETE FROM sent_mail WHERE workspace_id = ?", (workspace_id,))
        return len(rows)

    # ── reporting ──────────────────────────────────────────────────────────

    def stats(self, workspace_id: str = "local") -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS indexed,
                   COALESCE(SUM(got_reply), 0) AS replied,
                   MAX(sent_at) AS newest
            FROM sent_mail WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()
        indexed = int(row["indexed"] or 0)
        return {
            "indexed": indexed,
            "replied": int(row["replied"] or 0),
            "newest": str(row["newest"] or ""),
            "searchable_locally": True,
            "embeddings_used": False,
            "stored_redacted": True,
            "max_snippets_per_payload": MAX_SNIPPETS_IN_PAYLOAD,
        }
