from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .models import (
    ContactInput,
    DraftContent,
    IncomingMessage,
    SendResult,
    clean_text,
    normalize_email,
    parse_datetime,
    to_utc_iso,
)
from .schema import SCHEMA_SQL, SCHEMA_VERSION


class OutreachStore:
    """SQLite source of truth for one local user's outreach workspace."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = NORMAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.fts_enabled = False

    def __enter__(self) -> "OutreachStore":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        try:
            self.connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA_SQL)
        self._migrate_legacy_schema()
        try:
            self.connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS expert_chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_name,
                    expert_name,
                    content,
                    tags
                )
                """
            )
            self.fts_enabled = True
        except sqlite3.OperationalError:
            self.fts_enabled = False
        self.connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.connection.commit()
        if not self.fts_enabled:
            self.fts_enabled = self._table_exists("expert_chunks_fts")

    def _migrate_legacy_schema(self) -> None:
        additions = {
            "contacts": {
                "recipient_timezone": "TEXT NOT NULL DEFAULT ''",
                "outcome_label": "TEXT NOT NULL DEFAULT ''",
            },
            "campaigns": {
                "send_window_start": "TEXT NOT NULL DEFAULT '00:00'",
                "send_window_end": "TEXT NOT NULL DEFAULT '00:00'",
                "send_weekdays_json": "TEXT NOT NULL DEFAULT '[0, 1, 2, 3, 4, 5, 6]'",
                "experiment_hypothesis": "TEXT NOT NULL DEFAULT ''",
                "experiment_metric": "TEXT NOT NULL DEFAULT 'reply_rate'",
                "experiment_min_sample": "INTEGER NOT NULL DEFAULT 40",
                "control_variant": "TEXT NOT NULL DEFAULT 'A'",
            },
            "campaign_contacts": {
                "checkbox": "INTEGER NOT NULL DEFAULT 0",
            },
            "drafts": {
                "sending_started_at": "TEXT",
                "send_error": "TEXT NOT NULL DEFAULT ''",
                "revision": "INTEGER NOT NULL DEFAULT 1",
                "scheduled_at": "TEXT",
                "generation_meta_json": "TEXT NOT NULL DEFAULT '{}'",
            },
            "messages": {
                "idempotency_key": "TEXT NOT NULL DEFAULT ''",
                "variant_id": "TEXT NOT NULL DEFAULT ''",
                "template_id": "TEXT NOT NULL DEFAULT ''",
                "draft_revision": "INTEGER NOT NULL DEFAULT 0",
                "ai_provider_profile_id": "TEXT NOT NULL DEFAULT ''",
            },
            "email_templates": {
                "provenance_json": "TEXT NOT NULL DEFAULT '{}'",
                "version_no": "INTEGER NOT NULL DEFAULT 1",
            },
            "expert_chunks": {
                "source_url": "TEXT NOT NULL DEFAULT ''",
                "source_type": "TEXT NOT NULL DEFAULT 'notes'",
                "rights_basis": "TEXT NOT NULL DEFAULT 'user_provided'",
            },
            "discovery_runs": {
                "objective_prompt": "TEXT NOT NULL DEFAULT ''",
                "plan_json": "TEXT NOT NULL DEFAULT '{}'",
                "target_count": "INTEGER NOT NULL DEFAULT 100",
            },
        }
        for table, columns in additions.items():
            if not self._table_exists(table):
                continue
            existing = {
                str(row["name"])
                for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for name, definition in columns.items():
                if name not in existing:
                    self.connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                    )

    def _table_exists(self, name: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name = ? LIMIT 1", (name,)
        ).fetchone()
        return row is not None

    def _row(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        row = self.connection.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None

    def _rows(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(query, tuple(params)).fetchall()]

    @staticmethod
    def _like(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    # Contacts and campaign membership

    def upsert_contact(self, contact: ContactInput) -> str:
        contact = contact.normalized()
        now = to_utc_iso()
        existing = None
        if contact.email:
            existing = self._row(
                "SELECT * FROM contacts WHERE lower(email) = ?", (contact.email,)
            )
        if not existing and contact.linkedin_url:
            existing = self._row(
                "SELECT * FROM contacts WHERE lower(rtrim(linkedin_url, '/')) = ?",
                (contact.linkedin_url.lower().split("?", 1)[0].rstrip("/"),),
            )
        if not existing:
            existing = self._row(
                "SELECT * FROM contacts WHERE identity_key = ?", (contact.identity_key,)
            )

        fields = {
            "full_name": contact.full_name,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "company": contact.company,
            "title": contact.title,
            "category": contact.category,
            "route": contact.route,
            "linkedin_url": contact.linkedin_url,
            "public_hook": contact.public_hook,
            "hook_source": contact.hook_source,
            "hook_date": contact.hook_date,
            "tension": contact.tension,
            "identity_line": contact.identity_line,
            "contribution": contact.contribution,
            "questions_json": json.dumps(contact.questions, ensure_ascii=False),
            "notes": contact.notes,
            "source_ref": contact.source_ref,
            "source_json": json.dumps(contact.source_data, ensure_ascii=False, default=str),
            "recipient_timezone": contact.recipient_timezone,
            "outcome_label": contact.outcome_label,
        }
        if existing:
            contact_id = str(existing["id"])
            merged = {
                key: value if value not in ("", "[]", "{}") else existing.get(key, "")
                for key, value in fields.items()
            }
            assignments = ", ".join(f"{key} = ?" for key in merged)
            with self.transaction() as conn:
                conn.execute(
                    f"UPDATE contacts SET {assignments}, updated_at = ? WHERE id = ?",
                    (*merged.values(), now, contact_id),
                )
            return contact_id

        if not contact.full_name:
            raise ValueError("Contact full_name is required")
        contact_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO contacts (
                    id, identity_key, full_name, first_name, last_name, email, company,
                    title, category, route, linkedin_url, public_hook, hook_source,
                    hook_date, tension, identity_line, contribution, questions_json,
                    notes, source_ref, source_json, recipient_timezone, outcome_label,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (contact_id, contact.identity_key, *fields.values(), now, now),
            )
        return contact_id

    def get_contact(self, contact_id: str) -> dict[str, Any] | None:
        return self._row("SELECT * FROM contacts WHERE id = ?", (contact_id,))

    def create_campaign(
        self,
        *,
        name: str,
        daily_send_limit: int,
        timezone_name: str = "Asia/Kolkata",
        followup1_working_days: int = 4,
        followup2_working_days: int = 6,
        approval_mode: str = "each_message",
        variants: Iterable[str] = ("A", "B"),
        send_window_start: str = "00:00",
        send_window_end: str = "00:00",
        send_weekdays: Iterable[int] = (0, 1, 2, 3, 4, 5, 6),
        experiment_hypothesis: str = "",
        experiment_metric: str = "reply_rate",
        experiment_min_sample: int = 40,
        control_variant: str = "A",
    ) -> str:
        if daily_send_limit <= 0:
            raise ValueError("daily_send_limit must be positive")
        if approval_mode not in {"each_message", "whole_sequence"}:
            raise ValueError("approval_mode must be each_message or whole_sequence")
        if followup1_working_days < 1 or followup2_working_days < 1:
            raise ValueError("follow-up working days must be positive")
        normalized_variants = [clean_text(item) for item in variants if clean_text(item)]
        normalized_variants = list(dict.fromkeys(normalized_variants)) or ["A"]
        weekdays = sorted({int(day) for day in send_weekdays})
        if not weekdays or any(day < 0 or day > 6 for day in weekdays):
            raise ValueError("send_weekdays must contain values from 0 to 6")
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", send_window_start):
            raise ValueError("send_window_start must use HH:MM")
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", send_window_end):
            raise ValueError("send_window_end must use HH:MM")
        if control_variant not in normalized_variants:
            raise ValueError("control_variant must be one of the campaign variants")
        campaign_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (
                    id, name, daily_send_limit, timezone, followup1_working_days,
                    followup2_working_days, approval_mode, variants_json,
                    status, send_window_start, send_window_end, send_weekdays_json,
                    experiment_hypothesis, experiment_metric, experiment_min_sample,
                    control_variant, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    clean_text(name),
                    daily_send_limit,
                    timezone_name,
                    followup1_working_days,
                    followup2_working_days,
                    approval_mode,
                    json.dumps(normalized_variants),
                    send_window_start,
                    send_window_end,
                    json.dumps(weekdays),
                    clean_text(experiment_hypothesis),
                    experiment_metric,
                    max(10, int(experiment_min_sample)),
                    control_variant,
                    now,
                    now,
                ),
            )
        self.add_event(campaign_id, "campaign_created", {"name": name})
        return campaign_id

    def get_campaign(self, campaign_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        if not row:
            raise KeyError(f"Campaign not found: {campaign_id}")
        row["variants"] = json.loads(row.get("variants_json") or "[]")
        row["send_weekdays"] = json.loads(row.get("send_weekdays_json") or "[]")
        return row

    def list_campaigns(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str = "",
        search: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("c.status = ?")
            params.append(status)
        if search:
            where.append("c.name LIKE ? ESCAPE '\\'")
            params.append(self._like(search))
        clause = " WHERE " + " AND ".join(where) if where else ""
        total_row = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM campaigns c{clause}", params
        ).fetchone()
        rows = self._rows(
            f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = c.id) AS contact_count,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = c.id AND cc.status = 'replied') AS replied_count,
                   (SELECT COUNT(*) FROM messages m
                    JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
                    WHERE cc.campaign_id = c.id AND m.direction = 'outbound') AS sent_count
            FROM campaigns c
            {clause}
            ORDER BY c.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        for row in rows:
            row["variants"] = json.loads(row.get("variants_json") or "[]")
            row["send_weekdays"] = json.loads(row.get("send_weekdays_json") or "[]")
            row["contact_count"] = int(row.get("contact_count") or 0)
            row["replied_count"] = int(row.get("replied_count") or 0)
            row["sent_count"] = int(row.get("sent_count") or 0)
        return rows, int(total_row["count"] if total_row else 0)

    def update_campaign(self, campaign_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        changes = dict(changes)
        if "send_weekdays" in changes:
            weekdays = sorted({int(day) for day in changes.pop("send_weekdays")})
            if not weekdays or any(day < 0 or day > 6 for day in weekdays):
                raise ValueError("send_weekdays must contain values from 0 to 6")
            changes["send_weekdays_json"] = json.dumps(weekdays)
        allowed = {
            "name",
            "daily_send_limit",
            "timezone",
            "followup1_working_days",
            "followup2_working_days",
            "approval_mode",
            "status",
            "send_window_start",
            "send_window_end",
            "send_weekdays_json",
            "experiment_hypothesis",
            "experiment_metric",
            "experiment_min_sample",
            "control_variant",
        }
        values = {key: value for key, value in changes.items() if key in allowed and value is not None}
        if not values:
            return self.get_campaign(campaign_id)
        if "status" in values and values["status"] not in {"active", "paused", "archived"}:
            raise ValueError("Invalid campaign status")
        if "approval_mode" in values and values["approval_mode"] not in {
            "each_message",
            "whole_sequence",
        }:
            raise ValueError("Invalid approval mode")
        if "daily_send_limit" in values and int(values["daily_send_limit"]) <= 0:
            raise ValueError("daily_send_limit must be positive")
        for field in ("send_window_start", "send_window_end"):
            if field in values and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", str(values[field])):
                raise ValueError(f"{field} must use HH:MM")
        if "experiment_min_sample" in values and int(values["experiment_min_sample"]) < 10:
            raise ValueError("experiment_min_sample must be at least 10")
        if "control_variant" in values:
            campaign = self.get_campaign(campaign_id)
            if values["control_variant"] not in campaign["variants"]:
                raise ValueError("control_variant must be one of the campaign variants")
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE campaigns SET {assignments}, updated_at = ? WHERE id = ?",
                (*values.values(), to_utc_iso(), campaign_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Campaign not found: {campaign_id}")
        self.add_event(campaign_id, "campaign_updated", values)
        return self.get_campaign(campaign_id)

    def add_contact_to_campaign(self, campaign_id: str, contact_id: str) -> tuple[str, bool]:
        campaign = self.get_campaign(campaign_id)
        variants = campaign["variants"] or ["A"]
        bucket = int(
            hashlib.sha256(f"{campaign_id}:{contact_id}".encode()).hexdigest()[:12], 16
        )
        variant_id = str(variants[bucket % len(variants)])
        existing = self._row(
            "SELECT id FROM campaign_contacts WHERE campaign_id = ? AND contact_id = ?",
            (campaign_id, contact_id),
        )
        if existing:
            return str(existing["id"]), False
        row_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO campaign_contacts (
                    id, campaign_id, contact_id, variant_id, status,
                    next_action_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'new', ?, ?, ?)
                """,
                (row_id, campaign_id, contact_id, variant_id, now, now, now),
            )
        return row_id, True

    def get_campaign_contact(self, campaign_id: str, campaign_contact_id: str) -> dict[str, Any]:
        row = self._row(
            """
            SELECT cc.*, c.full_name, c.first_name, c.last_name, c.email, c.company,
                   c.title, c.category, c.route, c.linkedin_url, c.public_hook,
                   c.hook_source, c.hook_date, c.tension, c.identity_line,
                   c.contribution, c.questions_json, c.notes AS contact_notes, c.source_ref
                   , c.recipient_timezone, c.outcome_label
            FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id
            WHERE cc.campaign_id = ? AND cc.id = ?
            """,
            (campaign_id, campaign_contact_id),
        )
        if not row:
            raise KeyError(f"Campaign contact not found: {campaign_contact_id}")
        row["notes"] = row.pop("contact_notes", "")
        return row

    def list_campaign_contacts(
        self,
        campaign_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        search: str = "",
        status: str = "",
        category: str = "",
        variant_id: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        self.get_campaign(campaign_id)
        where = ["cc.campaign_id = ?"]
        params: list[Any] = [campaign_id]
        if search:
            value = self._like(search)
            where.append("(c.full_name LIKE ? ESCAPE '\\' OR c.email LIKE ? ESCAPE '\\' OR c.company LIKE ? ESCAPE '\\')")
            params.extend([value, value, value])
        if status:
            where.append("cc.status = ?")
            params.append(status)
        if category:
            where.append("c.category = ?")
            params.append(category)
        if variant_id:
            where.append("cc.variant_id = ?")
            params.append(variant_id)
        clause = " AND ".join(where)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*) AS count FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id WHERE {clause}
            """,
            params,
        ).fetchone()
        rows = self._rows(
            f"""
            SELECT cc.*, c.full_name, c.first_name, c.last_name, c.email, c.company,
                   c.title, c.category, c.route, c.linkedin_url, c.public_hook,
                   c.hook_source, c.hook_date, c.tension, c.identity_line,
                   c.contribution, c.questions_json, c.notes AS contact_notes, c.source_ref,
                   c.recipient_timezone, c.outcome_label,
                   (SELECT COUNT(*) FROM messages m WHERE m.campaign_contact_id = cc.id AND m.direction = 'outbound') AS sent_count
            FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id
            WHERE {clause}
            ORDER BY c.full_name, c.email
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        for row in rows:
            row["notes"] = row.pop("contact_notes", "")
            row["checkbox"] = bool(row.get("checkbox"))
            row["sent_count"] = int(row.get("sent_count") or 0)
        return rows, int(count_row["count"] if count_row else 0)

    def campaign_contacts(self, campaign_id: str) -> list[dict[str, Any]]:
        rows, _ = self.list_campaign_contacts(campaign_id, limit=100000)
        return rows

    def update_campaign_contact(
        self,
        campaign_id: str,
        campaign_contact_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        current = self.get_campaign_contact(campaign_id, campaign_contact_id)
        contact_fields = {
            "full_name",
            "first_name",
            "last_name",
            "email",
            "company",
            "title",
            "category",
            "route",
            "linkedin_url",
            "public_hook",
            "hook_source",
            "hook_date",
            "tension",
            "identity_line",
            "contribution",
            "notes",
            "recipient_timezone",
            "outcome_label",
        }
        membership_fields = {"checkbox", "poi_response", "meeting_transcript", "status"}
        contact_values = {
            key: clean_text(value) if key != "email" else normalize_email(value)
            for key, value in changes.items()
            if key in contact_fields and value is not None
        }
        membership_values = {
            key: int(bool(value)) if key == "checkbox" else clean_text(value)
            for key, value in changes.items()
            if key in membership_fields and value is not None
        }
        now = to_utc_iso()
        with self.transaction() as conn:
            if contact_values:
                assignments = ", ".join(f"{key} = ?" for key in contact_values)
                conn.execute(
                    f"UPDATE contacts SET {assignments}, updated_at = ? WHERE id = ?",
                    (*contact_values.values(), now, current["contact_id"]),
                )
            if membership_values:
                assignments = ", ".join(f"{key} = ?" for key in membership_values)
                conn.execute(
                    f"UPDATE campaign_contacts SET {assignments}, updated_at = ? WHERE id = ?",
                    (*membership_values.values(), now, campaign_contact_id),
                )
        self.add_event(
            campaign_id,
            "campaign_contact_updated",
            {"fields": sorted(set(contact_values) | set(membership_values))},
            campaign_contact_id=campaign_contact_id,
        )
        return self.get_campaign_contact(campaign_id, campaign_contact_id)

    # Draft lifecycle

    def save_draft(self, campaign_contact_id: str, draft: DraftContent) -> str:
        existing = self._row(
            "SELECT * FROM drafts WHERE campaign_contact_id = ? AND stage = ?",
            (campaign_contact_id, draft.stage),
        )
        now = to_utc_iso()
        if existing and existing.get("sent_at"):
            return str(existing["id"])
        if existing:
            draft_id = str(existing["id"])
            with self.transaction() as conn:
                conn.execute(
                    """
                    UPDATE drafts SET variant_id = ?, template_id = ?, subject = ?, body = ?,
                        quality_score = ?, sendable = ?, audit_json = ?, retrieval_refs_json = ?,
                        generation_meta_json = ?,
                        approval_status = 'pending', approved_at = NULL, sending_started_at = NULL,
                        send_error = '', revision = revision + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        draft.variant_id,
                        draft.template_id,
                        draft.subject,
                        draft.body,
                        draft.audit.score,
                        int(draft.audit.sendable),
                        draft.audit.to_json(),
                        json.dumps(draft.retrieval_refs),
                        json.dumps(draft.generation_meta, ensure_ascii=False, default=str),
                        now,
                        draft_id,
                    ),
                )
            return draft_id
        draft_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO drafts (
                    id, campaign_contact_id, stage, variant_id, template_id, subject,
                    body, quality_score, sendable, audit_json, retrieval_refs_json,
                    generation_meta_json, approval_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    draft_id,
                    campaign_contact_id,
                    draft.stage,
                    draft.variant_id,
                    draft.template_id,
                    draft.subject,
                    draft.body,
                    draft.audit.score,
                    int(draft.audit.sendable),
                    draft.audit.to_json(),
                    json.dumps(draft.retrieval_refs),
                    json.dumps(draft.generation_meta, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE campaign_contacts SET status = 'drafted', updated_at = ?
                WHERE id = ? AND status NOT IN ('replied', 'stopped', 'completed')
                """,
                (now, campaign_contact_id),
            )
        return draft_id

    def get_draft(self, campaign_contact_id: str, stage: str) -> dict[str, Any] | None:
        return self._row(
            "SELECT * FROM drafts WHERE campaign_contact_id = ? AND stage = ?",
            (campaign_contact_id, stage),
        )

    def get_draft_by_id(self, campaign_id: str, draft_id: str) -> dict[str, Any]:
        row = self._row(
            """
            SELECT d.*, cc.campaign_id, cc.contact_id, cc.status AS contact_status,
                   cc.variant_id AS assigned_variant, c.full_name, c.email, c.company,
                   c.category, c.route, c.public_hook, c.hook_source
            FROM drafts d
            JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
            JOIN contacts c ON c.id = cc.contact_id
            WHERE cc.campaign_id = ? AND d.id = ?
            """,
            (campaign_id, draft_id),
        )
        if not row:
            raise KeyError(f"Draft not found: {draft_id}")
        return self._decode_draft(row)

    @staticmethod
    def _decode_draft(row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        try:
            row["audit"] = json.loads(row.get("audit_json") or "{}")
        except json.JSONDecodeError:
            row["audit"] = {}
        try:
            row["retrieval_refs"] = json.loads(row.get("retrieval_refs_json") or "[]")
        except json.JSONDecodeError:
            row["retrieval_refs"] = []
        try:
            row["generation_meta"] = json.loads(row.get("generation_meta_json") or "{}")
        except json.JSONDecodeError:
            row["generation_meta"] = {}
        row["sendable"] = bool(row.get("sendable"))
        return row

    def list_drafts(
        self,
        campaign_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        stage: str = "",
        approval_status: str = "",
        sendable: bool | None = None,
        search: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        self.get_campaign(campaign_id)
        where = ["cc.campaign_id = ?"]
        params: list[Any] = [campaign_id]
        if stage:
            where.append("d.stage = ?")
            params.append(stage)
        if approval_status:
            where.append("d.approval_status = ?")
            params.append(approval_status)
        if sendable is not None:
            where.append("d.sendable = ?")
            params.append(int(sendable))
        if search:
            value = self._like(search)
            where.append("(c.full_name LIKE ? ESCAPE '\\' OR c.email LIKE ? ESCAPE '\\' OR c.company LIKE ? ESCAPE '\\')")
            params.extend([value, value, value])
        clause = " AND ".join(where)
        count_row = self.connection.execute(
            f"""
            SELECT COUNT(*) AS count FROM drafts d
            JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
            JOIN contacts c ON c.id = cc.contact_id
            WHERE {clause}
            """,
            params,
        ).fetchone()
        rows = self._rows(
            f"""
            SELECT d.*, c.full_name, c.email, c.company, c.category, c.route,
                   cc.status AS contact_status, cc.variant_id AS assigned_variant
            FROM drafts d
            JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
            JOIN contacts c ON c.id = cc.contact_id
            WHERE {clause}
            ORDER BY
                CASE d.stage WHEN 'initial' THEN 1 WHEN 'followup1' THEN 2 ELSE 3 END,
                c.full_name
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [self._decode_draft(row) for row in rows], int(
            count_row["count"] if count_row else 0
        )

    def update_draft_content(self, draft_id: str, draft: DraftContent) -> None:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE drafts SET subject = ?, body = ?, quality_score = ?, sendable = ?,
                    audit_json = ?, retrieval_refs_json = ?, approval_status = 'pending',
                    generation_meta_json = ?, approved_at = NULL, send_error = '',
                    revision = revision + 1, updated_at = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                (
                    draft.subject,
                    draft.body,
                    draft.audit.score,
                    int(draft.audit.sendable),
                    draft.audit.to_json(),
                    json.dumps(draft.retrieval_refs),
                    json.dumps(draft.generation_meta, ensure_ascii=False, default=str),
                    to_utc_iso(),
                    draft_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("A sent or missing draft cannot be edited")

    def schedule_drafts(
        self,
        campaign_id: str,
        *,
        draft_ids: Iterable[str],
        scheduled_at: datetime | None,
    ) -> dict[str, int]:
        ids = list(dict.fromkeys(draft_ids))
        if not ids:
            return {"scheduled": 0}
        placeholders = ",".join("?" for _ in ids)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE drafts SET scheduled_at = ?, updated_at = ?
                WHERE id IN ({placeholders}) AND sent_at IS NULL
                  AND campaign_contact_id IN (
                      SELECT id FROM campaign_contacts WHERE campaign_id = ?
                  )
                """,
                (
                    to_utc_iso(scheduled_at) if scheduled_at else None,
                    to_utc_iso(),
                    *ids,
                    campaign_id,
                ),
            )
        return {"scheduled": cursor.rowcount}

    def approve_drafts(
        self,
        campaign_id: str,
        *,
        stages: Iterable[str] = (),
        draft_ids: Iterable[str] = (),
    ) -> dict[str, int]:
        stage_list = list(dict.fromkeys(stages))
        id_list = list(dict.fromkeys(draft_ids))
        where = ["cc.campaign_id = ?", "d.sent_at IS NULL"]
        params: list[Any] = [campaign_id]
        selectors: list[str] = []
        if stage_list:
            selectors.append("d.stage IN (" + ",".join("?" for _ in stage_list) + ")")
            params.extend(stage_list)
        if id_list:
            selectors.append("d.id IN (" + ",".join("?" for _ in id_list) + ")")
            params.extend(id_list)
        if not selectors:
            return {"approved": 0, "blocked": 0}
        where.append("(" + " OR ".join(selectors) + ")")
        rows = self._rows(
            f"""
            SELECT d.id, d.sendable FROM drafts d
            JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
            WHERE {' AND '.join(where)}
            """,
            params,
        )
        approved_ids = [str(row["id"]) for row in rows if int(row["sendable"]) == 1]
        now = to_utc_iso()
        if approved_ids:
            placeholders = ",".join("?" for _ in approved_ids)
            with self.transaction() as conn:
                conn.execute(
                    f"""
                    UPDATE drafts SET approval_status = 'approved', approved_at = ?,
                        sending_started_at = NULL, send_error = '', updated_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    (now, now, *approved_ids),
                )
        return {"approved": len(approved_ids), "blocked": len(rows) - len(approved_ids)}

    def claim_draft_for_send(self, draft_id: str, now: datetime) -> bool:
        with self.transaction(immediate=True) as conn:
            cursor = conn.execute(
                """
                UPDATE drafts SET approval_status = 'sending', sending_started_at = ?, updated_at = ?
                WHERE id = ? AND approval_status = 'approved' AND sendable = 1 AND sent_at IS NULL
                """,
                (to_utc_iso(now), to_utc_iso(now), draft_id),
            )
        return cursor.rowcount == 1

    def mark_send_failed(self, draft_id: str, error: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE drafts SET approval_status = 'send_failed_review', send_error = ?,
                    sending_started_at = NULL, updated_at = ? WHERE id = ? AND sent_at IS NULL
                """,
                (clean_text(error)[:1000], to_utc_iso(), draft_id),
            )

    def get_message_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        return self._row(
            "SELECT * FROM messages WHERE idempotency_key = ?", (idempotency_key,)
        )

    def recover_stale_sending(self, campaign_id: str, *, before: datetime) -> int:
        """Move abandoned send claims to manual review, never to automatic retry."""
        with self.transaction(immediate=True) as conn:
            cursor = conn.execute(
                """
                UPDATE drafts SET approval_status = 'send_failed_review',
                    send_error = 'Stale send claim. Confirm provider state before retrying.',
                    sending_started_at = NULL, updated_at = ?
                WHERE id IN (
                    SELECT d.id FROM drafts d
                    JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
                    WHERE cc.campaign_id = ? AND d.approval_status = 'sending'
                      AND d.sending_started_at < ? AND d.sent_at IS NULL
                )
                """,
                (to_utc_iso(), campaign_id, to_utc_iso(before)),
            )
        return cursor.rowcount

    # Messages, replies, and queue state

    def last_outgoing(self, campaign_contact_id: str) -> dict[str, Any] | None:
        return self._row(
            """
            SELECT * FROM messages WHERE campaign_contact_id = ? AND direction = 'outbound'
            ORDER BY sent_at DESC, created_at DESC LIMIT 1
            """,
            (campaign_contact_id,),
        )

    def sent_count_between(
        self, campaign_id: str, start_utc: datetime, end_utc: datetime
    ) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS count FROM messages m
            JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
            WHERE cc.campaign_id = ? AND m.direction = 'outbound'
              AND m.sent_at >= ? AND m.sent_at < ?
            """,
            (campaign_id, to_utc_iso(start_utc), to_utc_iso(end_utc)),
        ).fetchone()
        return int(row["count"] if row else 0)

    def record_sent(
        self,
        *,
        campaign_contact_id: str,
        draft: dict[str, Any],
        result: SendResult,
        to_email: str,
        sent_at: datetime,
        next_action_at: datetime | None,
        final_status: str,
        idempotency_key: str,
    ) -> str:
        message_id = str(uuid.uuid4())
        sent_iso = to_utc_iso(sent_at)
        now = to_utc_iso()
        with self.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, campaign_contact_id, draft_id, stage, direction,
                    provider_message_id, thread_id, internet_message_id, idempotency_key,
                    to_email, subject, body, sent_at, variant_id, template_id,
                    draft_revision, ai_provider_profile_id, raw_json, created_at
                ) VALUES (?, ?, ?, ?, 'outbound', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    campaign_contact_id,
                    draft["id"],
                    draft["stage"],
                    result.provider_message_id,
                    result.thread_id,
                    result.internet_message_id,
                    idempotency_key,
                    normalize_email(to_email),
                    draft["subject"],
                    draft["body"],
                    sent_iso,
                    draft.get("variant_id", ""),
                    draft.get("template_id", ""),
                    int(draft.get("revision") or 0),
                    str((draft.get("generation_meta") or {}).get("provider_profile_id", "")),
                    json.dumps(result.raw, ensure_ascii=False, default=str),
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE drafts SET approval_status = 'sent', sent_at = ?, sending_started_at = NULL,
                    send_error = '', updated_at = ? WHERE id = ?
                """,
                (sent_iso, now, draft["id"]),
            )
            conn.execute(
                """
                UPDATE campaign_contacts SET status = ?, current_stage = ?,
                    next_action_at = ?, updated_at = ? WHERE id = ?
                """,
                (
                    final_status,
                    draft["stage"],
                    to_utc_iso(next_action_at) if next_action_at else None,
                    now,
                    campaign_contact_id,
                ),
            )
        return message_id

    def record_reply(self, campaign_id: str, incoming: IncomingMessage) -> list[str]:
        if incoming.provider_message_id:
            duplicate = self._row(
                "SELECT id FROM messages WHERE provider_message_id = ?",
                (incoming.provider_message_id,),
            )
            if duplicate:
                return []
        candidates: list[dict[str, Any]] = []
        if incoming.thread_id:
            candidates = self._rows(
                """
                SELECT DISTINCT m.campaign_contact_id FROM messages m
                JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
                WHERE m.thread_id = ? AND m.direction = 'outbound' AND cc.campaign_id = ?
                """,
                (incoming.thread_id, campaign_id),
            )
        if not candidates and incoming.from_email:
            candidates = self._rows(
                """
                SELECT cc.id AS campaign_contact_id FROM campaign_contacts cc
                JOIN contacts c ON c.id = cc.contact_id
                WHERE cc.campaign_id = ? AND lower(c.email) = ?
                  AND cc.status NOT IN ('replied', 'stopped', 'completed')
                ORDER BY cc.updated_at DESC LIMIT 1
                """,
                (campaign_id, normalize_email(incoming.from_email)),
            )
        updated: list[str] = []
        for candidate in candidates:
            campaign_contact_id = str(candidate["campaign_contact_id"])
            message_id = str(uuid.uuid4())
            received_iso = to_utc_iso(incoming.received_at)
            now = to_utc_iso()
            try:
                with self.transaction(immediate=True) as conn:
                    conn.execute(
                        """
                        INSERT INTO messages (
                            id, campaign_contact_id, stage, direction, provider_message_id,
                            thread_id, internet_message_id, from_email, subject, body,
                            received_at, raw_json, created_at
                        ) VALUES (?, ?, 'reply', 'inbound', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            message_id,
                            campaign_contact_id,
                            incoming.provider_message_id,
                            incoming.thread_id,
                            incoming.internet_message_id,
                            normalize_email(incoming.from_email),
                            incoming.subject,
                            incoming.body_preview,
                            received_iso,
                            json.dumps(incoming.raw, ensure_ascii=False, default=str),
                            now,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE campaign_contacts SET status = 'replied', replied_at = ?,
                            next_action_at = NULL, stopped_reason = 'reply_received',
                            poi_response = ?, updated_at = ? WHERE id = ?
                        """,
                        (received_iso, incoming.body_preview, now, campaign_contact_id),
                    )
                    conn.execute(
                        """
                        UPDATE drafts SET approval_status = 'cancelled_reply', updated_at = ?
                        WHERE campaign_contact_id = ? AND sent_at IS NULL
                          AND approval_status IN ('pending', 'approved', 'send_failed_review')
                        """,
                        (now, campaign_contact_id),
                    )
                updated.append(campaign_contact_id)
            except sqlite3.IntegrityError:
                continue
        return updated

    def earliest_outgoing_at(self, campaign_id: str) -> datetime | None:
        row = self.connection.execute(
            """
            SELECT MIN(m.sent_at) AS earliest FROM messages m
            JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
            WHERE cc.campaign_id = ? AND m.direction = 'outbound'
            """,
            (campaign_id,),
        ).fetchone()
        return parse_datetime(row["earliest"]) if row and row["earliest"] else None

    def send_queue(self, campaign_id: str, *, now: datetime) -> list[dict[str, Any]]:
        self.get_campaign(campaign_id)
        rows = self._rows(
            """
            SELECT cc.id AS campaign_contact_id, cc.status, cc.current_stage,
                   cc.next_action_at, cc.variant_id, c.full_name, c.email, c.company,
                   d.id AS draft_id, d.stage AS draft_stage, d.approval_status,
                   d.quality_score, d.sendable, d.scheduled_at, d.generation_meta_json
            FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id
            LEFT JOIN drafts d ON d.campaign_contact_id = cc.id AND d.stage =
                CASE cc.current_stage
                    WHEN '' THEN 'initial'
                    WHEN 'initial' THEN 'followup1'
                    WHEN 'followup1' THEN 'followup2'
                    ELSE 'none'
                END
            WHERE cc.campaign_id = ?
            ORDER BY COALESCE(cc.next_action_at, cc.created_at), c.full_name
            """,
            (campaign_id,),
        )
        for row in rows:
            due_at = parse_datetime(row.get("next_action_at"))
            scheduled_at = parse_datetime(row.get("scheduled_at"))
            effective_due = max(
                (value for value in (due_at, scheduled_at) if value is not None),
                default=None,
            )
            row["effective_due_at"] = to_utc_iso(effective_due) if effective_due else None
            row["is_due"] = bool(not effective_due or effective_due <= now)
            row["sendable"] = bool(row.get("sendable"))
            try:
                row["generation_meta"] = json.loads(row.get("generation_meta_json") or "{}")
            except json.JSONDecodeError:
                row["generation_meta"] = {}
        return rows

    # Events, reporting, and idempotency

    def add_event(
        self,
        campaign_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        campaign_contact_id: str | None = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO campaign_events (
                    id, campaign_id, campaign_contact_id, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    campaign_id,
                    campaign_contact_id,
                    event_type,
                    json.dumps(payload or {}, ensure_ascii=False, default=str),
                    to_utc_iso(),
                ),
            )

    def list_events(
        self, campaign_id: str, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        self.get_campaign(campaign_id)
        total = self.connection.execute(
            "SELECT COUNT(*) AS count FROM campaign_events WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        rows = self._rows(
            """
            SELECT * FROM campaign_events WHERE campaign_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (campaign_id, limit, offset),
        )
        for row in rows:
            try:
                row["payload"] = json.loads(row.get("payload_json") or "{}")
            except json.JSONDecodeError:
                row["payload"] = {}
        return rows, int(total["count"] if total else 0)

    def export_event_log(self, campaign_id: str) -> list[dict[str, Any]]:
        rows, _ = self.list_events(campaign_id, limit=100000)
        return list(reversed(rows))

    def campaign_summary(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.get_campaign(campaign_id)
        status_rows = self._rows(
            "SELECT status, COUNT(*) AS count FROM campaign_contacts WHERE campaign_id = ? GROUP BY status",
            (campaign_id,),
        )
        stage_rows = self._rows(
            """
            SELECT m.stage, COUNT(*) AS count FROM messages m
            JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
            WHERE cc.campaign_id = ? AND m.direction = 'outbound' GROUP BY m.stage
            """,
            (campaign_id,),
        )
        draft_rows = self._rows(
            """
            SELECT d.approval_status, COUNT(*) AS count FROM drafts d
            JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
            WHERE cc.campaign_id = ? GROUP BY d.approval_status
            """,
            (campaign_id,),
        )
        return {
            "campaign": campaign,
            "contacts": sum(int(row["count"]) for row in status_rows),
            "contact_status": {row["status"]: int(row["count"]) for row in status_rows},
            "messages_by_stage": {row["stage"]: int(row["count"]) for row in stage_rows},
            "draft_status": {
                row["approval_status"]: int(row["count"]) for row in draft_rows
            },
        }

    def dashboard_summary(self) -> dict[str, Any]:
        row = self.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM campaigns WHERE status = 'active') AS active_campaigns,
                (SELECT COUNT(*) FROM campaign_contacts) AS total_contacts,
                (SELECT COUNT(*) FROM campaign_contacts WHERE status = 'replied') AS replies,
                (SELECT COUNT(*) FROM messages WHERE direction = 'outbound') AS sent,
                (SELECT COUNT(*) FROM drafts WHERE approval_status = 'pending') AS pending_review,
                (SELECT COUNT(*) FROM campaign_contacts
                    WHERE status NOT IN ('replied', 'stopped', 'completed')
                      AND next_action_at IS NOT NULL AND next_action_at <= ?) AS due_now
            """,
            (to_utc_iso(),),
        ).fetchone()
        values = dict(row) if row else {}
        values = {key: int(value or 0) for key, value in values.items()}
        values["reply_rate"] = round(
            (values["replies"] / values["total_contacts"] * 100)
            if values["total_contacts"]
            else 0.0,
            1,
        )
        return values

    def ab_report(self, campaign_id: str) -> list[dict[str, Any]]:
        campaign = self.get_campaign(campaign_id)
        rows = self._rows(
            """
            SELECT cc.variant_id,
                   COUNT(*) AS contacts,
                   SUM(CASE WHEN cc.status = 'replied' THEN 1 ELSE 0 END) AS replies,
                   SUM(CASE WHEN EXISTS (
                       SELECT 1 FROM messages m WHERE m.campaign_contact_id = cc.id
                       AND m.direction = 'outbound' AND m.stage = 'initial'
                   ) THEN 1 ELSE 0 END) AS initial_sent
            FROM campaign_contacts cc WHERE cc.campaign_id = ?
            GROUP BY cc.variant_id ORDER BY cc.variant_id
            """,
            (campaign_id,),
        )
        for row in rows:
            contacts = int(row.get("contacts") or 0)
            replies = int(row.get("replies") or 0)
            initial_sent = int(row.get("initial_sent") or 0)
            row["contacts"] = contacts
            row["replies"] = replies
            row["initial_sent"] = initial_sent
            row["reply_rate"] = round(replies / initial_sent * 100, 1) if initial_sent else 0.0
            if initial_sent:
                probability = replies / initial_sent
                z = 1.96
                denominator = 1 + z * z / initial_sent
                centre = (probability + z * z / (2 * initial_sent)) / denominator
                margin = z * math.sqrt(
                    probability * (1 - probability) / initial_sent
                    + z * z / (4 * initial_sent * initial_sent)
                ) / denominator
                row["ci_low"] = round(max(0.0, centre - margin) * 100, 1)
                row["ci_high"] = round(min(1.0, centre + margin) * 100, 1)
            else:
                row["ci_low"] = 0.0
                row["ci_high"] = 0.0
        control = next(
            (row for row in rows if row["variant_id"] == campaign.get("control_variant")),
            rows[0] if rows else None,
        )
        control_rate = float(control.get("reply_rate") or 0.0) if control else 0.0
        minimum = int(campaign.get("experiment_min_sample") or 40)
        for row in rows:
            rate = float(row["reply_rate"])
            row["control_variant"] = campaign.get("control_variant", "A")
            row["lift_percentage_points"] = round(rate - control_rate, 1)
            row["relative_lift"] = (
                round((rate - control_rate) / control_rate * 100, 1) if control_rate else None
            )
            row["minimum_sample"] = minimum
            row["sample_status"] = "ready" if int(row["initial_sent"]) >= minimum else "collecting"
            row["hypothesis"] = campaign.get("experiment_hypothesis", "")
            row["primary_metric"] = campaign.get("experiment_metric", "reply_rate")
        return rows

    def get_idempotency(self, scope: str, request_key: str) -> dict[str, Any] | None:
        row = self._row(
            "SELECT response_json FROM idempotency_records WHERE scope = ? AND request_key = ?",
            (scope, request_key),
        )
        if not row:
            return None
        try:
            return json.loads(row["response_json"])
        except json.JSONDecodeError:
            return None

    def save_idempotency(self, scope: str, request_key: str, response: dict[str, Any]) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO idempotency_records (
                    scope, request_key, response_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (scope, request_key, json.dumps(response, default=str), to_utc_iso()),
            )

    # Provider observability and reusable local memory

    def record_provider_call(
        self,
        *,
        profile_id: str,
        provider_type: str,
        model: str,
        data_policy: str,
        status: str,
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        error: str = "",
        duration_ms: int = 0,
        workspace_id: str = "local",
    ) -> str:
        call_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO provider_calls (
                    id, workspace_id, profile_id, provider_type, model, data_policy,
                    status, request_json, response_json, error, duration_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    workspace_id,
                    profile_id,
                    provider_type,
                    model,
                    data_policy,
                    status,
                    json.dumps(request_payload or {}, ensure_ascii=False, default=str),
                    json.dumps(response_payload or {}, ensure_ascii=False, default=str),
                    clean_text(error)[:2000],
                    max(0, int(duration_ms)),
                    to_utc_iso(),
                ),
            )
        return call_id

    def list_provider_calls(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        profile_id: str = "",
        status: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []
        if profile_id:
            where.append("profile_id = ?")
            params.append(profile_id)
        if status:
            where.append("status = ?")
            params.append(status)
        clause = " WHERE " + " AND ".join(where) if where else ""
        total_row = self._row(f"SELECT COUNT(*) AS count FROM provider_calls{clause}", params)
        rows = self._rows(
            f"SELECT * FROM provider_calls{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        for row in rows:
            for source, target in (("request_json", "request"), ("response_json", "response")):
                try:
                    row[target] = json.loads(row.get(source) or "{}")
                except json.JSONDecodeError:
                    row[target] = {}
        return rows, int(total_row["count"] if total_row else 0)

    def add_memory_item(
        self,
        *,
        kind: str,
        content: str,
        scope: str = "global",
        tags: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
        confidence: float = 0.5,
        approved: bool = False,
        source_type: str = "observation",
        workspace_id: str = "local",
    ) -> str:
        normalized = clean_text(content)
        if not normalized:
            raise ValueError("Memory content is required")
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = to_utc_iso()
        existing = self._row(
            """
            SELECT id, confidence, approved FROM memory_items
            WHERE workspace_id = ? AND scope = ? AND kind = ? AND content_sha256 = ?
            """,
            (workspace_id, scope, kind, digest),
        )
        if existing:
            with self.transaction() as conn:
                conn.execute(
                    """
                    UPDATE memory_items SET confidence = ?, approved = ?, tags_json = ?,
                        metadata_json = ?, source_type = ?, updated_at = ? WHERE id = ?
                    """,
                    (
                        max(float(existing["confidence"]), min(1.0, max(0.0, confidence))),
                        int(bool(existing["approved"]) or approved),
                        json.dumps(list(dict.fromkeys(tags)), ensure_ascii=False),
                        json.dumps(metadata or {}, ensure_ascii=False, default=str),
                        source_type,
                        now,
                        existing["id"],
                    ),
                )
            return str(existing["id"])
        memory_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO memory_items (
                    id, workspace_id, scope, kind, content, content_sha256, tags_json,
                    metadata_json, confidence, approved, source_type, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    workspace_id,
                    scope,
                    kind,
                    normalized,
                    digest,
                    json.dumps(list(dict.fromkeys(tags)), ensure_ascii=False),
                    json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    min(1.0, max(0.0, confidence)),
                    int(approved),
                    source_type,
                    now,
                    now,
                ),
            )
        return memory_id

    @staticmethod
    def _decode_memory(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for source, target, fallback in (
            ("tags_json", "tags", []),
            ("metadata_json", "metadata", {}),
        ):
            try:
                result[target] = json.loads(result.get(source) or json.dumps(fallback))
            except json.JSONDecodeError:
                result[target] = fallback
        result["approved"] = bool(result.get("approved"))
        result["confidence"] = float(result.get("confidence") or 0.0)
        return result

    def search_memory_items(
        self,
        query: str = "",
        *,
        scope: str = "",
        kind: str = "",
        approved_only: bool = False,
        workspace_id: str = "local",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if scope:
            where.append("scope IN ('global', ?)")
            params.append(scope)
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if approved_only:
            where.append("approved = 1")
        rows = self._rows(
            f"SELECT * FROM memory_items WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT 1000",
            params,
        )
        tokens = {token for token in re.findall(r"[a-z0-9]{3,}", query.lower())}
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            decoded = self._decode_memory(row)
            haystack = " ".join(
                [decoded.get("content", ""), " ".join(decoded.get("tags", [])), decoded.get("kind", "")]
            ).lower()
            matched = sum(1 for token in tokens if token in haystack)
            if tokens and matched == 0:
                continue
            score = matched / max(1, len(tokens)) + decoded["confidence"] * 0.25 + (0.2 if decoded["approved"] else 0)
            decoded["relevance_score"] = round(score, 4)
            ranked.append((score, decoded))
        ranked.sort(key=lambda item: (item[0], item[1].get("updated_at", "")), reverse=True)
        total = len(ranked)
        return [item for _, item in ranked[offset : offset + limit]], total

    def set_memory_approval(self, memory_id: str, approved: bool) -> dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE memory_items SET approved = ?, updated_at = ? WHERE id = ?",
                (int(approved), to_utc_iso(), memory_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Memory item not found")
        row = self._row("SELECT * FROM memory_items WHERE id = ?", (memory_id,))
        return self._decode_memory(row or {})

    def memory_stats(self, *, workspace_id: str = "local") -> dict[str, Any]:
        rows = self._rows(
            """
            SELECT kind, COUNT(*) AS count, SUM(approved) AS approved
            FROM memory_items WHERE workspace_id = ? GROUP BY kind ORDER BY kind
            """,
            (workspace_id,),
        )
        return {
            "backend": "sqlite_local",
            "workspace_id": workspace_id,
            "total": sum(int(row["count"]) for row in rows),
            "approved": sum(int(row.get("approved") or 0) for row in rows),
            "by_kind": {row["kind"]: int(row["count"]) for row in rows},
        }

    # Public-web POI discovery

    @staticmethod
    def _decode_discovery_run(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["seed_urls"] = json.loads(result.pop("seed_urls_json", "[]") or "[]")
        result["allowed_domains"] = json.loads(
            result.pop("allowed_domains_json", "[]") or "[]"
        )
        result["errors"] = json.loads(result.pop("errors_json", "[]") or "[]")
        result["plan"] = json.loads(result.pop("plan_json", "{}") or "{}")
        result["obey_robots"] = bool(result.get("obey_robots"))
        return result

    @staticmethod
    def _decode_discovery_candidate(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["evidence"] = json.loads(result.pop("evidence_json", "{}") or "{}")
        result["source_data"] = json.loads(result.pop("source_json", "{}") or "{}")
        result["confidence"] = float(result.get("confidence") or 0)
        return result

    def contact_exclusion_records(self) -> list[dict[str, Any]]:
        """Return only the fields needed to stop rediscovery of existing CRM contacts."""
        return self._rows(
            """
            SELECT full_name AS name, email, company, title, linkedin_url
            FROM contacts
            """
        )

    def create_discovery_run(
        self,
        *,
        campaign_id: str,
        seed_urls: Sequence[str],
        allowed_domains: Sequence[str],
        category: str,
        route: str,
        max_pages: int,
        max_depth: int,
        obey_robots: bool,
        engine: str = "safe_http",
        objective_prompt: str = "",
        plan: dict[str, Any] | None = None,
        target_count: int = 100,
    ) -> str:
        self.get_campaign(campaign_id)
        run_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO discovery_runs (
                    id, campaign_id, status, engine, seed_urls_json,
                    allowed_domains_json, category, route, max_pages, max_depth,
                    obey_robots, objective_prompt, plan_json, target_count,
                    started_at, created_at, updated_at
                ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    campaign_id,
                    clean_text(engine),
                    json.dumps(list(seed_urls), ensure_ascii=False),
                    json.dumps(list(allowed_domains), ensure_ascii=False),
                    clean_text(category),
                    clean_text(route),
                    int(max_pages),
                    int(max_depth),
                    int(obey_robots),
                    clean_text(objective_prompt),
                    json.dumps(plan or {}, ensure_ascii=False, default=str),
                    int(target_count),
                    now,
                    now,
                    now,
                ),
            )
        return run_id

    def finish_discovery_run(
        self,
        run_id: str,
        *,
        status: str,
        pages_crawled: int,
        candidates_found: int,
        fresh_count: int,
        excluded_count: int,
        errors: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        if status not in {"completed", "partial", "failed"}:
            raise ValueError("Invalid discovery run status")
        now = to_utc_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE discovery_runs
                SET status = ?, pages_crawled = ?, candidates_found = ?,
                    fresh_count = ?, excluded_count = ?, errors_json = ?,
                    finished_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    int(pages_crawled),
                    int(candidates_found),
                    int(fresh_count),
                    int(excluded_count),
                    json.dumps(list(errors), ensure_ascii=False, default=str),
                    now,
                    now,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("Discovery run not found")
        return self.get_discovery_run(run_id)

    def get_discovery_run(self, run_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM discovery_runs WHERE id = ?", (run_id,))
        if not row:
            raise KeyError("Discovery run not found")
        return self._decode_discovery_run(row)

    def list_discovery_runs(
        self, campaign_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        self.get_campaign(campaign_id)
        total = self.connection.execute(
            "SELECT COUNT(*) AS count FROM discovery_runs WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        rows = self._rows(
            """
            SELECT * FROM discovery_runs WHERE campaign_id = ?
            ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (campaign_id, limit, offset),
        )
        return [self._decode_discovery_run(row) for row in rows], int(
            total["count"] if total else 0
        )

    def add_discovery_candidate(self, run_id: str, item: dict[str, Any]) -> str:
        candidate_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO discovery_candidates (
                    id, run_id, identity_key, full_name, first_name, last_name,
                    email, company, company_domain, title, category, route,
                    country, linkedin_url, source_url, public_hook, confidence,
                    status, exclusion_reason, evidence_json, source_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    run_id,
                    clean_text(item.get("identity_key")),
                    clean_text(item.get("full_name")),
                    clean_text(item.get("first_name")),
                    clean_text(item.get("last_name")),
                    normalize_email(item.get("email")),
                    clean_text(item.get("company")),
                    clean_text(item.get("company_domain")),
                    clean_text(item.get("title")),
                    clean_text(item.get("category")),
                    clean_text(item.get("route")),
                    clean_text(item.get("country")),
                    clean_text(item.get("linkedin_url")),
                    clean_text(item.get("source_url")),
                    clean_text(item.get("public_hook")),
                    float(item.get("confidence") or 0),
                    clean_text(item.get("status")) or "new",
                    clean_text(item.get("exclusion_reason")),
                    json.dumps(item.get("evidence") or {}, ensure_ascii=False, default=str),
                    json.dumps(item.get("source_data") or {}, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                existing = conn.execute(
                    """
                    SELECT id FROM discovery_candidates
                    WHERE run_id = ? AND identity_key = ?
                    """,
                    (run_id, clean_text(item.get("identity_key"))),
                ).fetchone()
                return str(existing["id"] if existing else "")
        return candidate_id

    def list_discovery_candidates(
        self,
        run_id: str,
        *,
        limit: int = 500,
        offset: int = 0,
        status: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        self.get_discovery_run(run_id)
        where = ["run_id = ?"]
        params: list[Any] = [run_id]
        if status:
            where.append("status = ?")
            params.append(status)
        clause = " AND ".join(where)
        total = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM discovery_candidates WHERE {clause}", params
        ).fetchone()
        rows = self._rows(
            f"""
            SELECT * FROM discovery_candidates WHERE {clause}
            ORDER BY (status = 'excluded'), confidence DESC, full_name
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [self._decode_discovery_candidate(row) for row in rows], int(
            total["count"] if total else 0
        )

    def discovery_candidates_by_id(
        self, run_id: str, candidate_ids: Sequence[str]
    ) -> list[dict[str, Any]]:
        unique = list(dict.fromkeys(str(item) for item in candidate_ids if item))
        if not unique:
            return []
        placeholders = ",".join("?" for _ in unique)
        rows = self._rows(
            f"""
            SELECT * FROM discovery_candidates
            WHERE run_id = ? AND id IN ({placeholders})
            ORDER BY confidence DESC, full_name
            """,
            (run_id, *unique),
        )
        return [self._decode_discovery_candidate(row) for row in rows]

    def set_discovery_candidate_status(
        self, run_id: str, candidate_ids: Sequence[str], status: str
    ) -> int:
        if status not in {"new", "approved", "rejected", "apollo_queued", "imported"}:
            raise ValueError("Invalid discovery candidate status")
        unique = list(dict.fromkeys(str(item) for item in candidate_ids if item))
        if not unique:
            return 0
        placeholders = ",".join("?" for _ in unique)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE discovery_candidates SET status = ?, updated_at = ?
                WHERE run_id = ? AND id IN ({placeholders}) AND status <> 'excluded'
                """,
                (status, to_utc_iso(), run_id, *unique),
            )
            return int(cursor.rowcount)

    # Research graph and context layer

    @staticmethod
    def _decode_research_entity(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["properties"] = json.loads(result.pop("properties_json", "{}") or "{}")
        result["confidence"] = float(result.get("confidence") or 0)
        result["source_count"] = int(result.get("source_count") or 0)
        return result

    @staticmethod
    def _decode_research_edge(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["properties"] = json.loads(result.pop("properties_json", "{}") or "{}")
        result["confidence"] = float(result.get("confidence") or 0)
        return result

    def upsert_research_entity(
        self,
        *,
        entity_type: str,
        canonical_key: str,
        name: str = "",
        properties: dict[str, Any] | None = None,
        confidence: float = 0,
        workspace_id: str = "local",
    ) -> str:
        entity_type = clean_text(entity_type).lower()
        canonical_key = clean_text(canonical_key).lower()
        workspace_id = clean_text(workspace_id) or "local"
        if not entity_type or not canonical_key:
            raise ValueError("Research entities require a type and canonical key")
        now = to_utc_iso()
        with self.transaction(immediate=True) as conn:
            existing = conn.execute(
                """
                SELECT * FROM research_entities
                WHERE workspace_id = ? AND entity_type = ? AND canonical_key = ?
                """,
                (workspace_id, entity_type, canonical_key),
            ).fetchone()
            if existing:
                current = json.loads(existing["properties_json"] or "{}")
                current.update(properties or {})
                conn.execute(
                    """
                    UPDATE research_entities
                    SET name = ?, properties_json = ?, confidence = ?,
                        source_count = source_count + 1, last_seen_at = ?
                    WHERE id = ?
                    """,
                    (
                        clean_text(name) or existing["name"],
                        json.dumps(current, ensure_ascii=False, default=str),
                        max(float(existing["confidence"] or 0), float(confidence or 0)),
                        now,
                        existing["id"],
                    ),
                )
                return str(existing["id"])
            entity_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO research_entities (
                    id, workspace_id, entity_type, canonical_key, name,
                    properties_json, confidence, source_count, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    entity_id,
                    workspace_id,
                    entity_type,
                    canonical_key,
                    clean_text(name),
                    json.dumps(properties or {}, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, float(confidence or 0))),
                    now,
                    now,
                ),
            )
            return entity_id

    def upsert_research_edge(
        self,
        *,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        properties: dict[str, Any] | None = None,
        confidence: float = 0,
        evidence_url: str = "",
        workspace_id: str = "local",
    ) -> str:
        relation_type = clean_text(relation_type).upper()
        workspace_id = clean_text(workspace_id) or "local"
        if not source_entity_id or not target_entity_id or not relation_type:
            raise ValueError("Research edges require source, target and relation")
        now = to_utc_iso()
        with self.transaction(immediate=True) as conn:
            existing = conn.execute(
                """
                SELECT * FROM research_edges
                WHERE workspace_id = ? AND source_entity_id = ?
                  AND target_entity_id = ? AND relation_type = ?
                """,
                (workspace_id, source_entity_id, target_entity_id, relation_type),
            ).fetchone()
            if existing:
                current = json.loads(existing["properties_json"] or "{}")
                current.update(properties or {})
                conn.execute(
                    """
                    UPDATE research_edges
                    SET properties_json = ?, confidence = ?, evidence_url = ?, last_seen_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(current, ensure_ascii=False, default=str),
                        max(float(existing["confidence"] or 0), float(confidence or 0)),
                        clean_text(evidence_url) or existing["evidence_url"],
                        now,
                        existing["id"],
                    ),
                )
                return str(existing["id"])
            edge_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO research_edges (
                    id, workspace_id, source_entity_id, target_entity_id,
                    relation_type, properties_json, confidence, evidence_url,
                    first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    workspace_id,
                    source_entity_id,
                    target_entity_id,
                    relation_type,
                    json.dumps(properties or {}, ensure_ascii=False, default=str),
                    max(0.0, min(1.0, float(confidence or 0))),
                    clean_text(evidence_url),
                    now,
                    now,
                ),
            )
            return edge_id

    def add_research_observation(
        self,
        *,
        entity_id: str,
        source_url: str,
        evidence: dict[str, Any],
        run_id: str | None = None,
        candidate_id: str | None = None,
        workspace_id: str = "local",
    ) -> str:
        payload = json.dumps(evidence or {}, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{clean_text(source_url)}\n{payload}".encode("utf-8")).hexdigest()
        observation_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO research_observations (
                    id, workspace_id, run_id, candidate_id, entity_id,
                    source_url, evidence_hash, evidence_json, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    clean_text(workspace_id) or "local",
                    run_id,
                    candidate_id,
                    entity_id,
                    clean_text(source_url),
                    digest,
                    payload,
                    to_utc_iso(),
                ),
            )
        return observation_id

    def research_graph(
        self,
        *,
        run_id: str = "",
        query: str = "",
        limit: int = 250,
        workspace_id: str = "local",
    ) -> dict[str, Any]:
        limit = max(1, min(500, int(limit)))
        workspace_id = clean_text(workspace_id) or "local"
        params: list[Any] = [workspace_id]
        where = ["e.workspace_id = ?"]
        if run_id:
            where.append(
                "e.id IN (SELECT entity_id FROM research_observations WHERE workspace_id = ? AND run_id = ?)"
            )
            params.extend([workspace_id, run_id])
        if query:
            token = self._like(clean_text(query))
            where.append("(e.name LIKE ? ESCAPE '\\' OR e.properties_json LIKE ? ESCAPE '\\')")
            params.extend([token, token])
        nodes = self._rows(
            f"""
            SELECT e.* FROM research_entities e
            WHERE {' AND '.join(where)}
            ORDER BY e.last_seen_at DESC LIMIT ?
            """,
            (*params, limit),
        )
        node_ids = [row["id"] for row in nodes]
        edges: list[dict[str, Any]] = []
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            edge_rows = self._rows(
                f"""
                SELECT * FROM research_edges
                WHERE workspace_id = ?
                  AND source_entity_id IN ({placeholders})
                  AND target_entity_id IN ({placeholders})
                ORDER BY last_seen_at DESC LIMIT ?
                """,
                (workspace_id, *node_ids, *node_ids, limit * 3),
            )
            edges = [self._decode_research_edge(row) for row in edge_rows]
        decoded_nodes = [self._decode_research_entity(row) for row in nodes]
        by_type: dict[str, int] = {}
        by_relation: dict[str, int] = {}
        for node in decoded_nodes:
            by_type[node["entity_type"]] = by_type.get(node["entity_type"], 0) + 1
        for edge in edges:
            by_relation[edge["relation_type"]] = by_relation.get(edge["relation_type"], 0) + 1
        return {
            "nodes": decoded_nodes,
            "edges": edges,
            "stats": {
                "nodes": len(decoded_nodes),
                "edges": len(edges),
                "by_type": by_type,
                "by_relation": by_relation,
            },
        }

    # Template and expert library

    def upsert_template(self, item: dict[str, Any]) -> None:
        required = {"id", "name", "stage", "variant_id", "subject_template", "body_template"}
        missing = sorted(field for field in required if not clean_text(item.get(field)))
        if missing:
            raise ValueError("Template is missing: " + ", ".join(missing))
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO email_templates (
                    id, name, category, route, stage, variant_id, subject_template,
                    body_template, tags_json, source_ref, provenance_json, version_no,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name, category = excluded.category, route = excluded.route,
                    stage = excluded.stage, variant_id = excluded.variant_id,
                    subject_template = excluded.subject_template,
                    body_template = excluded.body_template, tags_json = excluded.tags_json,
                    source_ref = excluded.source_ref, provenance_json = excluded.provenance_json,
                    version_no = email_templates.version_no + 1,
                    active = excluded.active, updated_at = excluded.updated_at
                WHERE email_templates.name <> excluded.name
                   OR email_templates.category <> excluded.category
                   OR email_templates.route <> excluded.route
                   OR email_templates.stage <> excluded.stage
                   OR email_templates.variant_id <> excluded.variant_id
                   OR email_templates.subject_template <> excluded.subject_template
                   OR email_templates.body_template <> excluded.body_template
                   OR email_templates.tags_json <> excluded.tags_json
                   OR email_templates.source_ref <> excluded.source_ref
                   OR email_templates.provenance_json <> excluded.provenance_json
                   OR email_templates.active <> excluded.active
                """,
                (
                    clean_text(item["id"]),
                    clean_text(item["name"]),
                    clean_text(item.get("category")) or "*",
                    clean_text(item.get("route")) or "*",
                    clean_text(item["stage"]),
                    clean_text(item["variant_id"]),
                    str(item["subject_template"]),
                    str(item["body_template"]),
                    json.dumps(item.get("tags") or [], ensure_ascii=False),
                    clean_text(item.get("source_ref")),
                    json.dumps(item.get("provenance") or {}, ensure_ascii=False),
                    int(item.get("version_no") or 1),
                    int(bool(item.get("active", True))),
                    now,
                    now,
                ),
            )

    def matching_templates(
        self, *, stage: str, route: str, category: str, variant_id: str
    ) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT * FROM email_templates
            WHERE active = 1 AND stage = ? AND variant_id = ?
              AND route IN (?, '*') AND category IN (?, '*')
            ORDER BY (route = ?) DESC, (category = ?) DESC, updated_at DESC
            """,
            (stage, variant_id, route, category, route, category),
        )

    def list_templates(
        self, *, limit: int = 100, offset: int = 0, active_only: bool = True
    ) -> tuple[list[dict[str, Any]], int]:
        where = " WHERE active = 1" if active_only else ""
        total = self.connection.execute(
            f"SELECT COUNT(*) AS count FROM email_templates{where}"
        ).fetchone()
        rows = self._rows(
            f"""
            SELECT * FROM email_templates{where}
            ORDER BY stage, route, variant_id, name LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        for row in rows:
            row["tags"] = json.loads(row.get("tags_json") or "[]")
            row["provenance"] = json.loads(row.get("provenance_json") or "{}")
            row["active"] = bool(row.get("active"))
        return rows, int(total["count"] if total else 0)

    def add_expert_chunk(
        self,
        *,
        document_name: str,
        content: str,
        expert_name: str = "",
        tags: str = "",
        source_ref: str = "",
        source_url: str = "",
        source_type: str = "notes",
        rights_basis: str = "user_provided",
    ) -> bool:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        chunk_id = str(uuid.uuid4())
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO expert_chunks (
                    id, document_name, expert_name, content, tags, source_ref,
                    source_url, source_type, rights_basis, content_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    clean_text(document_name),
                    clean_text(expert_name),
                    content.strip(),
                    clean_text(tags),
                    clean_text(source_ref),
                    clean_text(source_url),
                    clean_text(source_type) or "notes",
                    clean_text(rights_basis) or "user_provided",
                    digest,
                    to_utc_iso(),
                ),
            )
            inserted = cursor.rowcount == 1
            if inserted and self.fts_enabled:
                conn.execute(
                    """
                    INSERT INTO expert_chunks_fts (
                        chunk_id, document_name, expert_name, content, tags
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, document_name, expert_name, content, tags),
                )
        return inserted

    def search_expert_chunks(self, query: str, *, limit: int = 4) -> list[dict[str, Any]]:
        tokens = re.findall(r"[A-Za-z0-9]{3,}", query.lower())
        if self.fts_enabled and tokens:
            expression = " OR ".join(f'"{token}"' for token in tokens[:12])
            try:
                rows = self._rows(
                    """
                    SELECT e.*, bm25(expert_chunks_fts) AS rank
                    FROM expert_chunks_fts
                    JOIN expert_chunks e ON e.id = expert_chunks_fts.chunk_id
                    WHERE expert_chunks_fts MATCH ? ORDER BY rank LIMIT ?
                    """,
                    (expression, limit),
                )
                if rows:
                    return rows
            except sqlite3.OperationalError:
                pass
        if not tokens:
            return self._rows(
                "SELECT * FROM expert_chunks ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        clauses = " OR ".join("lower(content) LIKE ?" for _ in tokens[:6])
        return self._rows(
            f"SELECT * FROM expert_chunks WHERE {clauses} ORDER BY created_at DESC LIMIT ?",
            (*[f"%{token}%" for token in tokens[:6]], limit),
        )

    def expert_source_summary(self) -> dict[str, int]:
        row = self.connection.execute(
            """
            SELECT COUNT(DISTINCT document_name) AS documents, COUNT(*) AS chunks
            FROM expert_chunks
            """
        ).fetchone()
        return {
            "documents": int(row["documents"] or 0) if row else 0,
            "chunks": int(row["chunks"] or 0) if row else 0,
        }
