"""Inventory-driven subject access and deletion.

A privacy request is not a pile of ad-hoc DELETE statements. One registry lists
where personal data can live, the same registry drives access and deletion, and
a deletion receipt stores only counts/status — never the data it just removed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urlsplit, urlunsplit

from .ai.context import ContextLayer
from .ai.log import EgressLog
from .ai.recall import SentMailIndex
from .outreach.store import OutreachStore

DELETE_CONFIRMATION = "DELETE SUBJECT DATA"
MAX_TRACE_BYTES = 10 * 1024 * 1024
MAX_TRACE_FILES = 10_000
MAX_STRUCTURED_FILES = 5_000
MAX_STRUCTURED_FILE_BYTES = 25 * 1024 * 1024

REQUIRED_PRIVACY_STORES = (
    "sent_mail_recall",
    "ai_context",
    "ai_egress",
    "subject_artifacts",
    "structured_exports",
    "crawler_frontier",
    "browser_traces",
    "outreach_crm",
)


class PrivacyError(ValueError):
    """A privacy request is malformed, unsafe, or cannot be certified complete."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _uniq(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PrivacyError(f"Subject URL must be an absolute http(s) URL: {text!r}")
    host = parsed.hostname.lower().rstrip(".").encode("idna").decode("ascii")
    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path.rstrip("/") or "/", "", ""))


@dataclass(frozen=True, slots=True)
class SubjectIdentity:
    workspace_id: str = "local"
    emails: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    contact_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    entity_ids: tuple[str, ...] = ()
    sales_lead_ids: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "SubjectIdentity":
        workspace = str(value.get("workspace_id") or "local").strip() or "local"
        emails = _uniq(
            str(item or "").strip().lower()
            for item in value.get("emails", [])
            if str(item or "").strip()
        )
        for email in emails:
            if "@" not in email or len(email) > 320:
                raise PrivacyError(f"Invalid subject email: {email!r}")
        urls = _uniq(_url(item) for item in value.get("urls", []) if str(item or "").strip())
        contact_ids = _uniq(str(item or "").strip() for item in value.get("contact_ids", []))
        candidate_ids = _uniq(str(item or "").strip() for item in value.get("candidate_ids", []))
        entity_ids = _uniq(str(item or "").strip() for item in value.get("entity_ids", []))
        sales_lead_ids = _uniq(str(item or "").strip() for item in value.get("sales_lead_ids", []))
        identity = cls(
            workspace_id=workspace,
            emails=emails,
            urls=urls,
            contact_ids=contact_ids,
            candidate_ids=candidate_ids,
            entity_ids=entity_ids,
            sales_lead_ids=sales_lead_ids,
        )
        if not identity.tokens:
            raise PrivacyError(
                "A privacy request needs a verified strong identifier: email, URL, or stable record id. "
                "Names are deliberately not accepted for destructive matching."
            )
        return identity

    @property
    def tokens(self) -> tuple[str, ...]:
        return _uniq(
            (
                *self.emails,
                *self.urls,
                *self.contact_ids,
                *self.candidate_ids,
                *self.entity_ids,
                *self.sales_lead_ids,
            )
        )

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "workspace_id": self.workspace_id,
                "emails": sorted(self.emails),
                "urls": sorted(self.urls),
                "contact_ids": sorted(self.contact_ids),
                "candidate_ids": sorted(self.candidate_ids),
                "entity_ids": sorted(self.entity_ids),
                "sales_lead_ids": sorted(self.sales_lead_ids),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class PrivacyRecord:
    store: str
    record_class: str
    provenance: str
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "store": self.store,
            "record_class": self.record_class,
            "provenance": self.provenance,
            "count": len(self.items),
            "items": list(self.items),
        }


class PrivacyAdapter(Protocol):
    name: str
    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]: ...
    def delete(self, subject: SubjectIdentity) -> dict[str, int]: ...


def _placeholders(values: Iterable[Any]) -> str:
    materialized = tuple(values)
    return ",".join("?" for _ in materialized)


def _like_token(value: str) -> str:
    """Literal LIKE pattern for exact strong identifiers embedded in text/JSON."""
    escaped = str(value).lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _token_clause(columns: Iterable[str], subject: SubjectIdentity) -> tuple[str, tuple[Any, ...]]:
    tokens = subject.tokens
    clauses: list[str] = []
    params: list[Any] = []
    for column in columns:
        for token in tokens:
            clauses.append(f"lower({column}) LIKE ? ESCAPE '\\'")
            params.append(_like_token(token))
    return " OR ".join(clauses), tuple(params)


def _redact_subject_text(value: object, subject: SubjectIdentity) -> str:
    text = str(value or "")
    for token in sorted(subject.tokens, key=len, reverse=True):
        if token:
            text = re.sub(re.escape(token), "[deleted-subject]", text, flags=re.IGNORECASE)
    return text


def _scrub_subject(value: object, subject: SubjectIdentity) -> str:
    """Keep operational errors useful without preserving the deleted identifiers."""
    return _redact_subject_text(value, subject)[:1000]


class OutreachPrivacyAdapter:
    """Structured CRM/discovery/research records linked by strong identifiers."""

    name = "outreach_crm"

    def __init__(self, store: OutreachStore) -> None:
        self.store = store

    def _contacts(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if subject.contact_ids:
            clauses.append(f"id IN ({_placeholders(subject.contact_ids)})")
            params.extend(subject.contact_ids)
        if subject.emails:
            clauses.append(f"lower(email) IN ({_placeholders(subject.emails)})")
            params.extend(subject.emails)
        if subject.urls:
            normalized = tuple(url.lower().rstrip("/") for url in subject.urls)
            clauses.append(
                f"lower(rtrim(linkedin_url, '/')) IN ({_placeholders(normalized)})"
            )
            params.extend(normalized)
        if not clauses:
            return []
        return [
            dict(row)
            for row in self.store.connection.execute(
                "SELECT * FROM contacts WHERE " + " OR ".join(clauses),
                tuple(params),
            ).fetchall()
        ]

    def _candidates(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if subject.candidate_ids:
            clauses.append(f"id IN ({_placeholders(subject.candidate_ids)})")
            params.extend(subject.candidate_ids)
        if subject.emails:
            clauses.append(f"lower(email) IN ({_placeholders(subject.emails)})")
            params.extend(subject.emails)
        if subject.urls:
            normalized = tuple(url.lower().rstrip("/") for url in subject.urls)
            clauses.append(
                f"lower(rtrim(linkedin_url, '/')) IN ({_placeholders(normalized)})"
            )
            params.extend(normalized)
        if not clauses:
            return []
        return [
            dict(row)
            for row in self.store.connection.execute(
                "SELECT * FROM discovery_candidates WHERE " + " OR ".join(clauses),
                tuple(params),
            ).fetchall()
        ]

    def _entity_ids(
        self,
        subject: SubjectIdentity,
        contacts: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
    ) -> tuple[str, ...]:
        keys = {
            str(row.get("identity_key") or "")
            for row in (*contacts, *candidates)
            if row.get("identity_key")
        }
        keys.update(subject.urls)
        ids = set(subject.entity_ids)
        if keys:
            rows = self.store.connection.execute(
                f"""
                SELECT id FROM research_entities
                WHERE workspace_id = ? AND canonical_key IN ({_placeholders(keys)})
                """,
                (subject.workspace_id, *keys),
            ).fetchall()
            ids.update(str(row["id"]) for row in rows)
        return _uniq(ids)

    def _sales(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = [subject.workspace_id]
        if subject.sales_lead_ids:
            clauses.append(f"id IN ({_placeholders(subject.sales_lead_ids)})")
            params.extend(subject.sales_lead_ids)
        if subject.emails:
            clauses.append(f"lower(email) IN ({_placeholders(subject.emails)})")
            params.extend(subject.emails)
        if not clauses:
            return []
        return [
            dict(row)
            for row in self.store.connection.execute(
                "SELECT * FROM sales_leads WHERE workspace_id = ? AND (" + " OR ".join(clauses) + ")",
                tuple(params),
            ).fetchall()
        ]

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        contacts = self._contacts(subject)
        candidates = self._candidates(subject)
        contact_ids = tuple(str(row["id"]) for row in contacts)
        candidate_ids = tuple(str(row["id"]) for row in candidates)
        entity_ids = self._entity_ids(subject, contacts, candidates)
        sales = self._sales(subject)
        records: list[PrivacyRecord] = []

        def add(record_class: str, rows: list[dict[str, Any]], provenance: str) -> None:
            if rows:
                records.append(PrivacyRecord(self.name, record_class, provenance, rows))

        add("contact", contacts, "contacts exact email/url/stable id")
        if contact_ids:
            memberships = [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM campaign_contacts WHERE contact_id IN ({_placeholders(contact_ids)})",
                    contact_ids,
                ).fetchall()
            ]
            add("campaign_membership", memberships, "campaign_contacts.contact_id")
            membership_ids = tuple(str(row["id"]) for row in memberships)
            if membership_ids:
                for table, record_class in (
                    ("drafts", "draft"),
                    ("messages", "message"),
                    ("campaign_events", "campaign_event"),
                ):
                    rows = [
                        dict(row)
                        for row in self.store.connection.execute(
                            f"SELECT * FROM {table} WHERE campaign_contact_id IN ({_placeholders(membership_ids)})",
                            membership_ids,
                        ).fetchall()
                    ]
                    add(record_class, rows, f"{table}.campaign_contact_id")

        add("discovery_candidate", candidates, "discovery_candidates exact email/url/stable id")

        if entity_ids:
            entities = [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM research_entities WHERE workspace_id = ? AND id IN ({_placeholders(entity_ids)})",
                    (subject.workspace_id, *entity_ids),
                ).fetchall()
            ]
            add("research_entity", entities, "research entity stable id/canonical key")
            edges = [
                dict(row)
                for row in self.store.connection.execute(
                    f"""
                    SELECT * FROM research_edges
                    WHERE workspace_id = ?
                      AND (source_entity_id IN ({_placeholders(entity_ids)})
                           OR target_entity_id IN ({_placeholders(entity_ids)}))
                    """,
                    (subject.workspace_id, *entity_ids, *entity_ids),
                ).fetchall()
            ]
            add("research_edge", edges, "research edge touching subject entity")
            observations = [
                dict(row)
                for row in self.store.connection.execute(
                    f"""
                    SELECT * FROM research_observations
                    WHERE workspace_id = ? AND entity_id IN ({_placeholders(entity_ids)})
                    """,
                    (subject.workspace_id, *entity_ids),
                ).fetchall()
            ]
            add("research_observation", observations, "research observation for subject entity")

        add("sales_lead", sales, "sales_leads exact email/stable id")

        # Personal data that is not structurally attached to a contact row still
        # needs the same access/deletion inventory. These tables have either an
        # exact recipient email column or bounded text/JSON written by this app.
        direct_specs = (
            ("email_contact_permissions", ("email",), "email_permission"),
            ("email_suppressions", ("email",), "email_suppression"),
            ("email_unsubscribe_tokens", ("email",), "unsubscribe_token"),
            ("email_send_jobs", ("to_email",), "email_send_job"),
            ("email_delivery_events", ("recipient_email",), "email_delivery_event"),
            ("memory_items", ("content", "metadata_json"), "memory_item"),
            ("provider_calls", ("request_json", "response_json", "error"), "provider_call"),
            ("ai_messages", ("content",), "ai_chat_message"),
            ("sales_setter_activity", ("notes",), "sales_activity_note"),
        )
        for table, columns, record_class in direct_specs:
            clause, params = _token_clause(columns, subject)
            if not clause:
                continue
            workspace_sql = ""
            workspace_params: tuple[Any, ...] = ()
            if table in {"memory_items", "provider_calls", "sales_setter_activity"}:
                workspace_sql = "workspace_id = ? AND "
                workspace_params = (subject.workspace_id,)
            rows = [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM {table} WHERE {workspace_sql}({clause})",
                    (*workspace_params, *params),
                ).fetchall()
            ]
            add(record_class, rows, f"{table} exact strong identifier in owned fields")

        # Historical/control rows can carry the subject without a direct FK.
        # They are inventoried separately because destructive cleanup differs:
        # run/event history is redacted in place, while cache/chunk rows are removed.
        residual_specs = (
            (
                "discovery_runs",
                ("objective_prompt", "plan_json", "seed_urls_json", "allowed_domains_json", "errors_json"),
                "discovery_run_metadata",
            ),
            ("campaign_events", ("payload_json",), "campaign_event_payload"),
            ("idempotency_records", ("response_json",), "idempotency_response"),
            ("expert_chunks", ("content", "source_ref", "source_url"), "expert_chunk"),
        )
        for table, columns, record_class in residual_specs:
            clause, params = _token_clause(columns, subject)
            if not clause:
                continue
            rows = [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM {table} WHERE {clause}", params
                ).fetchall()
            ]
            add(record_class, rows, f"{table} strong identifier in retained text/JSON")

        # If any message in a chat mentions the subject, remove/access the whole
        # chat. Assistant replies can repeat the same fact without repeating the
        # exact identifier, and retaining half a conversation is a privacy leak.
        clause, params = _token_clause(("content",), subject)
        if clause:
            chats = [
                dict(row)
                for row in self.store.connection.execute(
                    f"""
                    SELECT c.* FROM ai_chats c
                    WHERE c.workspace_id = ?
                      AND c.id IN (SELECT chat_id FROM ai_messages WHERE {clause})
                    """,
                    (subject.workspace_id, *params),
                ).fetchall()
            ]
            add("ai_chat", chats, "chat contains a message matching a strong identifier")
        return records

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        contacts = self._contacts(subject)
        candidates = self._candidates(subject)
        contact_ids = tuple(str(row["id"]) for row in contacts)
        candidate_ids = tuple(str(row["id"]) for row in candidates)
        entity_ids = self._entity_ids(subject, contacts, candidates)
        sales = self._sales(subject)
        sales_ids = tuple(str(row["id"]) for row in sales)

        direct_specs = (
            ("email_contact_permissions", ("email",)),
            ("email_suppressions", ("email",)),
            ("email_unsubscribe_tokens", ("email",)),
            ("email_send_jobs", ("to_email",)),
            ("email_delivery_events", ("recipient_email",)),
            ("memory_items", ("content", "metadata_json")),
            ("provider_calls", ("request_json", "response_json", "error")),
            ("sales_setter_activity", ("notes",)),
        )
        direct_matches: dict[str, tuple[str, tuple[Any, ...], str, tuple[Any, ...]]] = {}
        for table, columns in direct_specs:
            clause, params = _token_clause(columns, subject)
            if not clause:
                continue
            workspace_sql = ""
            workspace_params: tuple[Any, ...] = ()
            if table in {"memory_items", "provider_calls", "sales_setter_activity"}:
                workspace_sql = "workspace_id = ? AND "
                workspace_params = (subject.workspace_id,)
            direct_matches[table] = (clause, params, workspace_sql, workspace_params)

        chat_clause, chat_params = _token_clause(("content",), subject)
        chat_ids: tuple[str, ...] = ()
        if chat_clause:
            rows = self.store.connection.execute(
                f"""
                SELECT DISTINCT c.id FROM ai_chats c
                JOIN ai_messages m ON m.chat_id = c.id
                WHERE c.workspace_id = ? AND ({chat_clause})
                """,
                (subject.workspace_id, *chat_params),
            ).fetchall()
            chat_ids = tuple(str(row["id"]) for row in rows)

        residual_specs = (
            (
                "discovery_runs",
                ("objective_prompt", "plan_json", "seed_urls_json", "allowed_domains_json", "errors_json"),
                "redact",
            ),
            ("campaign_events", ("payload_json",), "redact"),
            ("idempotency_records", ("response_json",), "delete"),
            ("expert_chunks", ("content", "source_ref", "source_url"), "delete"),
        )
        residual_matches: dict[str, tuple[tuple[str, ...], str, list[dict[str, Any]]]] = {}
        for table, columns, action in residual_specs:
            clause, params = _token_clause(columns, subject)
            if not clause:
                continue
            rows = [
                dict(row)
                for row in self.store.connection.execute(
                    f"SELECT * FROM {table} WHERE {clause}", params
                ).fetchall()
            ]
            if rows:
                residual_matches[table] = (columns, action, rows)

        counts = {
            "contacts": len(contact_ids),
            "discovery_candidates": len(candidate_ids),
            "research_entities": len(entity_ids),
            "sales_leads": len(sales_ids),
            "ai_chats": len(chat_ids),
        }
        with self.store.transaction(immediate=True) as conn:
            if contact_ids:
                conn.execute(
                    f"DELETE FROM contacts WHERE id IN ({_placeholders(contact_ids)})",
                    contact_ids,
                )
            if candidate_ids:
                conn.execute(
                    f"DELETE FROM discovery_candidates WHERE id IN ({_placeholders(candidate_ids)})",
                    candidate_ids,
                )
            if entity_ids:
                conn.execute(
                    f"DELETE FROM research_entities WHERE workspace_id = ? AND id IN ({_placeholders(entity_ids)})",
                    (subject.workspace_id, *entity_ids),
                )
            if sales_ids:
                conn.execute(
                    f"DELETE FROM sales_leads WHERE workspace_id = ? AND id IN ({_placeholders(sales_ids)})",
                    (subject.workspace_id, *sales_ids),
                )
            if chat_ids:
                conn.execute(
                    f"DELETE FROM ai_chats WHERE workspace_id = ? AND id IN ({_placeholders(chat_ids)})",
                    (subject.workspace_id, *chat_ids),
                )
            for table, (clause, params, workspace_sql, workspace_params) in direct_matches.items():
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE {workspace_sql}({clause})",
                    (*workspace_params, *params),
                )
                counts[table] = int(cursor.rowcount or 0)

            for table, (columns, action, rows) in residual_matches.items():
                if action == "delete":
                    if table == "idempotency_records":
                        keys = tuple((str(row["scope"]), str(row["request_key"])) for row in rows)
                        for scope, request_key in keys:
                            conn.execute(
                                "DELETE FROM idempotency_records WHERE scope = ? AND request_key = ?",
                                (scope, request_key),
                            )
                    else:
                        ids = tuple(str(row["id"]) for row in rows)
                        if ids:
                            conn.execute(
                                f"DELETE FROM {table} WHERE id IN ({_placeholders(ids)})",
                                ids,
                            )
                else:
                    for row in rows:
                        values = [_redact_subject_text(row.get(column), subject) for column in columns]
                        assignments = ", ".join(f"{column} = ?" for column in columns)
                        conn.execute(
                            f"UPDATE {table} SET {assignments} WHERE id = ?",
                            (*values, str(row["id"])),
                        )
                counts[table] = len(rows)
        return counts


class CrawlerPrivacyAdapter:
    """Exact subject URLs from the durable crawl frontier/cache."""

    name = "crawler_frontier"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _rows(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        if not self.path.exists() or not subject.urls:
            return []
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                f"SELECT * FROM crawl_frontier WHERE url IN ({_placeholders(subject.urls)})",
                subject.urls,
            ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            connection.close()

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._rows(subject)
        return (
            [PrivacyRecord(self.name, "crawl_url", "exact canonical subject URL", rows)]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows = self._rows(subject)
        if not rows:
            return {"crawl_urls": 0}
        hosts = _uniq(str(row["host"]) for row in rows)
        connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"DELETE FROM crawl_frontier WHERE url IN ({_placeholders(subject.urls)})",
                subject.urls,
            )
            for host in hosts:
                remaining = connection.execute(
                    "SELECT 1 FROM crawl_frontier WHERE host = ? LIMIT 1", (host,)
                ).fetchone()
                if remaining is None:
                    connection.execute("DELETE FROM crawl_host_pace WHERE host = ?", (host,))
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return {"crawl_urls": len(rows)}


class TracePrivacyAdapter:
    """Run-level deletion for traces containing a strong subject identifier.

    Trace JSONL is append-only. Rewriting selected lines would break its audit
    integrity, so an explicit privacy deletion removes the whole matching run.
    """

    name = "browser_traces"

    def __init__(self, data_root: Path | str) -> None:
        self.root = Path(data_root)

    def _safe_run(self, path: Path) -> Path | None:
        try:
            root = self.root.resolve()
            run = path.parent.resolve()
        except OSError:
            return None
        if run == root or root not in run.parents or path.is_symlink() or path.parent.is_symlink():
            return None
        return run

    def _matches(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        if not self.root.exists():
            return []
        tokens = tuple(token.lower() for token in subject.tokens if token)
        if not tokens:
            return []
        matched: list[dict[str, Any]] = []
        seen_runs: set[str] = set()
        for index, trace in enumerate(self.root.rglob("trace.jsonl")):
            if index >= MAX_TRACE_FILES:
                raise PrivacyError("Trace inventory exceeded the safe scan limit")
            run = self._safe_run(trace)
            if run is None or str(run) in seen_runs:
                continue
            candidates = [trace, *run.glob("*.txt")]
            hit_files: list[str] = []
            for candidate in candidates:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                try:
                    if candidate.stat().st_size > MAX_TRACE_BYTES:
                        continue
                    text = candidate.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    continue
                if any(token in text for token in tokens):
                    hit_files.append(candidate.name)
            if hit_files:
                seen_runs.add(str(run))
                matched.append(
                    {
                        "run": str(run.relative_to(self.root.resolve())),
                        "matched_files": sorted(set(hit_files)),
                    }
                )
        return matched

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._matches(subject)
        return (
            [PrivacyRecord(self.name, "trace_run", "exact strong identifier in trace/capture text", rows)]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows = self._matches(subject)
        deleted = 0
        root = self.root.resolve()
        for row in rows:
            run = (root / str(row["run"])).resolve()
            if run == root or root not in run.parents or run.is_symlink():
                raise PrivacyError("Refusing unsafe trace deletion path")
            if run.exists():
                shutil.rmtree(run)
                deleted += 1
        return {"trace_runs": deleted}


class SentMailPrivacyAdapter:
    """Redacted recall still keeps the CRM membership id and must be forgettable."""

    name = "sent_mail_recall"

    def __init__(self, recall: SentMailIndex, outreach: OutreachStore) -> None:
        self.recall = recall
        self.outreach = outreach

    def _membership_ids(self, subject: SubjectIdentity) -> tuple[str, ...]:
        contacts = OutreachPrivacyAdapter(self.outreach)._contacts(subject)
        contact_ids = tuple(str(row["id"]) for row in contacts)
        if not contact_ids:
            return ()
        rows = self.outreach.connection.execute(
            f"SELECT id FROM campaign_contacts WHERE contact_id IN ({_placeholders(contact_ids)})",
            contact_ids,
        ).fetchall()
        return _uniq(str(row["id"]) for row in rows)

    def _rows(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        memberships = self._membership_ids(subject)
        if not memberships:
            return []
        return [
            dict(row)
            for row in self.recall.connection.execute(
                f"""
                SELECT message_id, workspace_id, campaign_id, campaign_contact_id,
                       template_id, variant_id, stage, category, route, sent_at
                FROM sent_mail
                WHERE workspace_id = ?
                  AND campaign_contact_id IN ({_placeholders(memberships)})
                """,
                (subject.workspace_id, *memberships),
            ).fetchall()
        ]

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._rows(subject)
        return (
            [PrivacyRecord(
                self.name,
                "redacted_sent_mail",
                "sent-mail index linked by campaign_contact_id",
                rows,
            )]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        memberships = self._membership_ids(subject)
        deleted = sum(self.recall.forget_contact(item) for item in memberships)
        return {"redacted_sent_mail": deleted}


class AIContextPrivacyAdapter:
    """Delete task-state rows whose owned context contains a strong identifier."""

    name = "ai_context"

    def __init__(self, context: ContextLayer) -> None:
        self.context = context

    def _rows(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        clause, params = _token_clause(
            ("title", "steps", "decisions", "facts", "summary"), subject
        )
        if not clause:
            return []
        rows = self.context.connection.execute(
            f"SELECT * FROM ai_task_state WHERE workspace_id = ? AND ({clause})",
            (subject.workspace_id, *params),
        ).fetchall()
        return [dict(row) for row in rows]

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._rows(subject)
        return (
            [PrivacyRecord(
                self.name,
                "agent_task_state",
                "strong identifier embedded in locally owned task context",
                rows,
            )]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows = self._rows(subject)
        ids = tuple(str(row["id"]) for row in rows)
        if not ids:
            return {"agent_task_state": 0}
        cursor = self.context.connection.execute(
            f"DELETE FROM ai_task_state WHERE workspace_id = ? AND id IN ({_placeholders(ids)})",
            (subject.workspace_id, *ids),
        )
        return {"agent_task_state": int(cursor.rowcount or 0)}


class AIEgressPrivacyAdapter:
    """Exact outbound provider payload/response audit rows containing the subject."""

    name = "ai_egress"

    def __init__(self, egress: EgressLog) -> None:
        self.egress = egress

    def _rows(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        clause, params = _token_clause(
            ("payload", "payload_summary", "response_text", "findings", "error"),
            subject,
        )
        if not clause:
            return []
        rows = self.egress.connection.execute(
            f"SELECT * FROM ai_egress_log WHERE workspace_id = ? AND ({clause})",
            (subject.workspace_id, *params),
        ).fetchall()
        return [dict(row) for row in rows]

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._rows(subject)
        return (
            [PrivacyRecord(
                self.name,
                "ai_egress_record",
                "strong identifier in exact outbound/returned AI audit material",
                rows,
            )]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows = self._rows(subject)
        ids = tuple(str(row["id"]) for row in rows)
        if not ids:
            return {"ai_egress_records": 0}
        with self.egress.connection.transaction() as conn:
            cursor = conn.execute(
                f"DELETE FROM ai_egress_log WHERE workspace_id = ? AND id IN ({_placeholders(ids)})",
                (subject.workspace_id, *ids),
            )
        return {"ai_egress_records": int(cursor.rowcount or 0)}


class SubjectArtifactPrivacyAdapter:
    """Files explicitly tagged as belonging to one subject.

    Image/video/distribution stores do not have a safe subject key today. A
    filename or prompt search would be destructive guesswork. Any workflow that
    creates a subject-specific file registers it here at creation time, giving
    deletion an exact, auditable key rather than fuzzy matching.
    """

    name = "subject_artifacts"

    def __init__(self, data_root: Path | str, database_path: Path | str) -> None:
        self.root = Path(data_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None, timeout=5
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS subject_artifacts (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                subject_fingerprint TEXT NOT NULL,
                record_class TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(workspace_id, subject_fingerprint, relative_path)
            );
            CREATE INDEX IF NOT EXISTS ix_subject_artifacts_subject
            ON subject_artifacts(workspace_id, subject_fingerprint);
            """
        )

    def close(self) -> None:
        self.connection.close()

    def _safe_file(self, path: Path | str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved_root = self.root.resolve()
        resolved = candidate.resolve()
        if resolved_root not in resolved.parents or resolved == resolved_root:
            raise PrivacyError("Subject artifact must live under the application data directory")
        if candidate.is_symlink() or (resolved.exists() and not resolved.is_file()):
            raise PrivacyError("Subject artifact must be a regular non-symlink file")
        return resolved

    def register(
        self,
        subject: SubjectIdentity,
        path: Path | str,
        *,
        record_class: str,
    ) -> str:
        resolved = self._safe_file(path)
        if not resolved.exists():
            raise PrivacyError("Cannot register a subject artifact that does not exist")
        artifact_id = str(uuid.uuid4())
        relative = str(resolved.relative_to(self.root.resolve()))
        self.connection.execute(
            """
            INSERT INTO subject_artifacts(
                id, workspace_id, subject_fingerprint, record_class, relative_path, created_at
            ) VALUES(?,?,?,?,?,?)
            ON CONFLICT(workspace_id, subject_fingerprint, relative_path) DO UPDATE SET
                record_class=excluded.record_class
            """,
            (
                artifact_id,
                subject.workspace_id,
                subject.fingerprint,
                str(record_class or "artifact")[:100],
                relative,
                _now(),
            ),
        )
        row = self.connection.execute(
            """
            SELECT id FROM subject_artifacts
            WHERE workspace_id = ? AND subject_fingerprint = ? AND relative_path = ?
            """,
            (subject.workspace_id, subject.fingerprint, relative),
        ).fetchone()
        return str(row["id"]) if row else artifact_id

    def _rows(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, workspace_id, record_class, relative_path, created_at
            FROM subject_artifacts
            WHERE workspace_id = ? AND subject_fingerprint = ?
            """,
            (subject.workspace_id, subject.fingerprint),
        ).fetchall()
        return [dict(row) for row in rows]

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._rows(subject)
        return (
            [PrivacyRecord(
                self.name,
                "generated_subject_artifact",
                "artifact explicitly registered to subject fingerprint",
                rows,
            )]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows = self._rows(subject)
        deleted_files = 0
        for row in rows:
            path = self._safe_file(str(row["relative_path"]))
            if path.exists():
                path.unlink()
                deleted_files += 1
        self.connection.execute(
            "DELETE FROM subject_artifacts WHERE workspace_id = ? AND subject_fingerprint = ?",
            (subject.workspace_id, subject.fingerprint),
        )
        return {"artifact_rows": len(rows), "artifact_files": deleted_files}


class StructuredExportPrivacyAdapter:
    """Exact-token cleanup for CSV exports/queues under application-owned roots.

    CSVs are row stores too. A queue/export may contain several people, so the
    whole file is not deleted: only rows containing a verified strong subject
    identifier are removed and the file is atomically replaced.
    """

    name = "structured_exports"

    def __init__(self, roots: Iterable[Path | str]) -> None:
        unique: list[Path] = []
        seen: set[str] = set()
        for value in roots:
            root = Path(value)
            try:
                resolved = root.resolve()
            except OSError:
                continue
            key = str(resolved)
            if key not in seen:
                seen.add(key)
                unique.append(resolved)
        self.roots = tuple(unique)

    def _files(self) -> list[tuple[Path, Path]]:
        found: list[tuple[Path, Path]] = []
        seen_files: set[str] = set()
        for root in self.roots:
            if not root.exists() or root.is_symlink():
                continue
            for path in root.rglob("*.csv"):
                if len(found) >= MAX_STRUCTURED_FILES:
                    raise PrivacyError("Structured-export inventory exceeded the safe file limit")
                try:
                    resolved = path.resolve()
                    size = path.stat().st_size
                except OSError:
                    continue
                if path.is_symlink() or root not in resolved.parents:
                    continue
                if str(resolved) in seen_files:
                    continue
                seen_files.add(str(resolved))
                if size > MAX_STRUCTURED_FILE_BYTES:
                    raise PrivacyError(f"Structured export exceeds the safe scan size: {resolved}")
                found.append((root, resolved))
        return found

    @staticmethod
    def _row_matches(row: list[str], subject: SubjectIdentity) -> bool:
        tokens = tuple(token.lower() for token in subject.tokens if token)
        return any(token in str(cell).lower() for cell in row for token in tokens)

    @staticmethod
    def _read(path: Path) -> list[list[str]]:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [list(row) for row in csv.reader(handle)]
        except (OSError, UnicodeError, csv.Error) as exc:
            raise PrivacyError(f"Could not safely read structured export {path}") from exc

    def _matches(self, subject: SubjectIdentity) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        for root, path in self._files():
            rows = self._read(path)
            for index, row in enumerate(rows, start=1):
                if self._row_matches(row, subject):
                    matches.append(
                        {
                            "root": str(root),
                            "path": str(path.relative_to(root)),
                            "row": index,
                            "values": row,
                        }
                    )
        return matches

    def find(self, subject: SubjectIdentity) -> list[PrivacyRecord]:
        rows = self._matches(subject)
        return (
            [PrivacyRecord(
                self.name,
                "csv_row",
                "verified strong identifier in application-owned CSV row",
                rows,
            )]
            if rows
            else []
        )

    def delete(self, subject: SubjectIdentity) -> dict[str, int]:
        rows_deleted = 0
        files_changed = 0
        for root, path in self._files():
            rows = self._read(path)
            kept = [row for row in rows if not self._row_matches(row, subject)]
            removed = len(rows) - len(kept)
            if not removed:
                continue
            temporary = path.with_name(f".{path.name}.privacy-{uuid.uuid4().hex}.tmp")
            try:
                with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
                    csv.writer(handle).writerows(kept)
                    handle.flush()
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            rows_deleted += removed
            files_changed += 1
        return {"csv_rows": rows_deleted, "csv_files": files_changed}


class PrivacyRequestStore:
    """Non-personal request/receipt ledger used for safe retry."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None, timeout=5
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS privacy_requests (
                id TEXT PRIMARY KEY,
                subject_fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                store_names_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS privacy_results (
                request_id TEXT NOT NULL,
                store_name TEXT NOT NULL,
                status TEXT NOT NULL,
                counts_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(request_id, store_name),
                FOREIGN KEY(request_id) REFERENCES privacy_requests(id) ON DELETE CASCADE
            );
            """
        )

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def create(self, fingerprint: str, store_names: Iterable[str]) -> str:
        request_id = str(uuid.uuid4())
        now = _now()
        with self._lock:
            self.connection.execute(
                "INSERT INTO privacy_requests(id, subject_fingerprint, status, store_names_json, created_at, updated_at)"
                " VALUES(?,?,'pending',?,?,?)",
                (request_id, fingerprint, json.dumps(list(store_names)), now, now),
            )
        return request_id

    def get(self, request_id: str) -> dict[str, Any]:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM privacy_requests WHERE id = ?", (request_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Privacy request not found")
        item = dict(row)
        item["store_names"] = json.loads(item.pop("store_names_json"))
        return item

    def results(self, request_id: str) -> dict[str, dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM privacy_results WHERE request_id = ?", (request_id,)
            ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            item["counts"] = json.loads(item.pop("counts_json"))
            result[str(item["store_name"])] = item
        return result

    def set_result(
        self,
        request_id: str,
        store_name: str,
        *,
        status: str,
        counts: dict[str, int] | None = None,
        error: str = "",
    ) -> None:
        now = _now()
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO privacy_results(request_id, store_name, status, counts_json, error, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(request_id, store_name) DO UPDATE SET
                    status=excluded.status,
                    counts_json=excluded.counts_json,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    request_id,
                    store_name,
                    status,
                    json.dumps(counts or {}, sort_keys=True),
                    str(error)[:1000],
                    now,
                ),
            )

    def set_status(self, request_id: str, status: str) -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE privacy_requests SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), request_id),
            )


class PrivacyService:
    """One registry drives access, preview, deletion and retry."""

    def __init__(
        self,
        *,
        adapters: Iterable[PrivacyAdapter],
        requests: PrivacyRequestStore,
        owned_resources: Iterable[Any] = (),
    ) -> None:
        materialized = tuple(adapters)
        names = [adapter.name for adapter in materialized]
        if len(names) != len(set(names)):
            raise PrivacyError("Privacy adapter names must be unique")
        if "outreach_crm" in names and names[-1] != "outreach_crm":
            raise PrivacyError(
                "outreach_crm must be the final privacy adapter so retry identifiers "
                "survive every auxiliary-store cleanup"
            )
        self.adapters = materialized
        self.requests = requests
        self._owned_resources = tuple(owned_resources)

    @classmethod
    def for_local(
        cls,
        outreach: OutreachStore,
        *,
        data_dir: Path | str,
        ai_context: ContextLayer | None = None,
        ai_recall: SentMailIndex | None = None,
        ai_egress: EgressLog | None = None,
        export_dir: Path | str | None = None,
    ) -> "PrivacyService":
        root = Path(data_dir)
        owned: list[Any] = []
        if ai_context is None:
            ai_context = ContextLayer(root / "ai_context.db")
            owned.append(ai_context)
        if ai_recall is None:
            ai_recall = SentMailIndex(root / "ai_recall.db")
            owned.append(ai_recall)
        if ai_egress is None:
            ai_egress = EgressLog(root / "ai_egress.db")
            owned.append(ai_egress)
        artifacts = SubjectArtifactPrivacyAdapter(
            root, root / "subject_artifacts.sqlite3"
        )
        owned.append(artifacts)
        adapters: tuple[PrivacyAdapter, ...] = (
            SentMailPrivacyAdapter(ai_recall, outreach),
            AIContextPrivacyAdapter(ai_context),
            AIEgressPrivacyAdapter(ai_egress),
            artifacts,
            StructuredExportPrivacyAdapter(
                (root, Path(export_dir)) if export_dir is not None else (root,)
            ),
            CrawlerPrivacyAdapter(root / "crawler_frontier.sqlite3"),
            TracePrivacyAdapter(root),
            # Deliberately last. Once CRM ids are gone, redacted recall rows
            # cannot be joined back to the person for a later retry.
            OutreachPrivacyAdapter(outreach),
        )
        names = tuple(adapter.name for adapter in adapters)
        if names != REQUIRED_PRIVACY_STORES:
            raise PrivacyError(
                "Privacy store registry drifted from REQUIRED_PRIVACY_STORES"
            )
        return cls(
            adapters=adapters,
            requests=PrivacyRequestStore(root / "privacy_requests.sqlite3"),
            owned_resources=owned,
        )

    def close(self) -> None:
        self.requests.close()
        for resource in reversed(self._owned_resources):
            close = getattr(resource, "close", None)
            if callable(close):
                close()

    def register_artifact(
        self,
        subject: SubjectIdentity,
        path: Path | str,
        *,
        record_class: str,
    ) -> str:
        adapter = next(
            (
                item
                for item in self.adapters
                if isinstance(item, SubjectArtifactPrivacyAdapter)
            ),
            None,
        )
        if adapter is None:
            raise PrivacyError("Subject artifact registry is unavailable")
        return adapter.register(subject, path, record_class=record_class)

    def access(self, subject: SubjectIdentity) -> dict[str, Any]:
        stores: list[dict[str, Any]] = []
        total = 0
        for adapter in self.adapters:
            records = [record.to_dict() for record in adapter.find(subject)]
            count = sum(int(record["count"]) for record in records)
            total += count
            stores.append({"store": adapter.name, "count": count, "records": records})
        return {
            "workspace_id": subject.workspace_id,
            "subject_fingerprint": subject.fingerprint,
            "total_records": total,
            "stores": stores,
        }

    def preview(self, subject: SubjectIdentity) -> dict[str, Any]:
        inventory = self.access(subject)
        request_id = self.requests.create(
            subject.fingerprint, (adapter.name for adapter in self.adapters)
        )
        return {
            "request_id": request_id,
            "status": "pending",
            "confirmation_required": DELETE_CONFIRMATION,
            "inventory": inventory,
        }

    def delete(
        self,
        request_id: str,
        subject: SubjectIdentity,
        *,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != DELETE_CONFIRMATION:
            raise PrivacyError(f"Deletion requires confirmation: {DELETE_CONFIRMATION}")
        request = self.requests.get(request_id)
        if request["subject_fingerprint"] != subject.fingerprint:
            raise PrivacyError("Subject identifiers do not match the deletion preview")
        prior = self.requests.results(request_id)
        adapter_by_name = {adapter.name: adapter for adapter in self.adapters}
        failures: list[str] = []
        for store_name in request["store_names"]:
            previous = prior.get(store_name)
            if previous and previous["status"] == "success":
                continue

            # CRM deletion is the irreversible identity anchor. If an auxiliary
            # store failed, keep those CRM ids intact so the exact same preview
            # can be retried safely instead of losing its join keys.
            if store_name == "outreach_crm" and failures:
                self.requests.set_result(
                    request_id,
                    store_name,
                    status="pending",
                    error="waiting for auxiliary privacy stores to succeed",
                )
                continue

            adapter = adapter_by_name.get(store_name)
            if adapter is None:
                self.requests.set_result(
                    request_id,
                    store_name,
                    status="failed",
                    error="registered privacy store is unavailable",
                )
                failures.append(store_name)
                continue
            try:
                counts = adapter.delete(subject)
            except Exception as exc:  # one failed store must not create false global success
                self.requests.set_result(
                    request_id,
                    store_name,
                    status="failed",
                    error=_scrub_subject(exc, subject),
                )
                failures.append(store_name)
            else:
                self.requests.set_result(
                    request_id,
                    store_name,
                    status="success",
                    counts=counts,
                )
        results = self.requests.results(request_id)
        complete = all(
            results.get(name, {}).get("status") == "success"
            for name in request["store_names"]
        )
        self.requests.set_status(request_id, "complete" if complete else "partial")
        return {
            "request_id": request_id,
            "status": "complete" if complete else "partial",
            "complete": complete,
            "stores": [
                {
                    "store": name,
                    "status": results.get(name, {}).get("status", "pending"),
                    "counts": results.get(name, {}).get("counts", {}),
                    "error": results.get(name, {}).get("error", ""),
                }
                for name in request["store_names"]
            ],
        }
