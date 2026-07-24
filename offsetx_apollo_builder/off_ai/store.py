from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from ..outreach.models import to_utc_iso
from .schema import OFF_AI_SCHEMA_SQL


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return fallback


class OffAIStore:
    """Source of truth for the extractable OFF_AI Studio domain."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = NORMAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self._lock = threading.RLock()

    def initialize(self) -> None:
        with self._lock:
            self.connection.executescript(OFF_AI_SCHEMA_SQL)
            self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self.connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                yield self.connection
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def _row(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None

    def _rows(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _like(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    # Projects

    def create_project(
        self, *, name: str, description: str = "", instructions: str = ""
    ) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_projects (
                    id, name, description, instructions, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, name.strip(), description.strip(), instructions.strip(), now, now),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM off_ai_projects WHERE id = ?", (project_id,))
        if not row:
            raise KeyError("AI project not found")
        return self._decode_project(row)

    def list_projects(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        where = "" if include_archived else "WHERE p.archived = 0"
        rows = self._rows(
            f"""
            SELECT p.*,
                   COUNT(c.id) AS conversation_count,
                   MAX(c.updated_at) AS last_conversation_at
            FROM off_ai_projects p
            LEFT JOIN off_ai_conversations c
              ON c.project_id = p.id AND c.archived = 0
            {where}
            GROUP BY p.id
            ORDER BY COALESCE(MAX(c.updated_at), p.updated_at) DESC, p.name
            """
        )
        return [self._decode_project(row) for row in rows]

    def update_project(self, project_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "instructions", "archived"}
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_project(project_id)
        if "name" in values and not str(values["name"]).strip():
            raise ValueError("Project name is required")
        if "archived" in values:
            values["archived"] = int(bool(values["archived"]))
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE off_ai_projects SET {assignments}, updated_at = ? WHERE id = ?",
                (*values.values(), to_utc_iso(), project_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("AI project not found")
        return self.get_project(project_id)

    @staticmethod
    def _decode_project(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["archived"] = bool(result.get("archived"))
        result["conversation_count"] = int(result.get("conversation_count") or 0)
        return result

    # Conversations and messages

    def create_conversation(
        self,
        *,
        title: str = "New chat",
        project_id: str = "",
        selected_profile_id: str = "",
        task_type: str = "public_general",
        data_class: str = "public",
    ) -> dict[str, Any]:
        if project_id:
            self.get_project(project_id)
        conversation_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_conversations (
                    id, project_id, title, selected_profile_id, task_type,
                    data_class, created_at, updated_at
                ) VALUES (?, NULLIF(?, ''), ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    project_id,
                    title.strip() or "New chat",
                    selected_profile_id.strip(),
                    task_type,
                    data_class,
                    now,
                    now,
                ),
            )
        self.get_context("conversation", conversation_id, create=True)
        return self.get_conversation(conversation_id)

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        row = self._row(
            """
            SELECT c.*, p.name AS project_name,
                   (SELECT COUNT(*) FROM off_ai_messages m
                    WHERE m.conversation_id = c.id) AS message_count
            FROM off_ai_conversations c
            LEFT JOIN off_ai_projects p ON p.id = c.project_id
            WHERE c.id = ?
            """,
            (conversation_id,),
        )
        if not row:
            raise KeyError("AI conversation not found")
        return self._decode_conversation(row)

    def list_conversations(
        self,
        *,
        project_id: str = "",
        search: str = "",
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1 = 1"]
        params: list[Any] = []
        if not include_archived:
            where.append("c.archived = 0")
        if project_id:
            where.append("c.project_id = ?")
            params.append(project_id)
        if search:
            value = self._like(search)
            where.append(
                """(
                    c.title LIKE ? ESCAPE '\\'
                    OR EXISTS (
                        SELECT 1 FROM off_ai_messages sm
                        WHERE sm.conversation_id = c.id
                          AND sm.content LIKE ? ESCAPE '\\'
                    )
                )"""
            )
            params.extend([value, value])
        clause = " AND ".join(where)
        count = self._row(
            f"SELECT COUNT(*) AS count FROM off_ai_conversations c WHERE {clause}",
            params,
        )
        rows = self._rows(
            f"""
            SELECT c.*, p.name AS project_name,
                   (SELECT COUNT(*) FROM off_ai_messages m
                    WHERE m.conversation_id = c.id) AS message_count,
                   (SELECT substr(m2.content, 1, 180) FROM off_ai_messages m2
                    WHERE m2.conversation_id = c.id
                    ORDER BY m2.created_at DESC, m2.id DESC LIMIT 1) AS last_message
            FROM off_ai_conversations c
            LEFT JOIN off_ai_projects p ON p.id = c.project_id
            WHERE {clause}
            ORDER BY c.pinned DESC, c.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [self._decode_conversation(row) for row in rows], int(
            count["count"] if count else 0
        )

    def update_conversation(
        self, conversation_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        allowed = {
            "title",
            "project_id",
            "selected_profile_id",
            "task_type",
            "data_class",
            "pinned",
            "archived",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_conversation(conversation_id)
        if "title" in values and not str(values["title"]).strip():
            raise ValueError("Conversation title is required")
        if "project_id" in values:
            project_id = str(values["project_id"] or "")
            if project_id:
                self.get_project(project_id)
            values["project_id"] = project_id or None
        for field in ("pinned", "archived"):
            if field in values:
                values[field] = int(bool(values[field]))
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE off_ai_conversations
                SET {assignments}, updated_at = ?
                WHERE id = ?
                """,
                (*values.values(), to_utc_iso(), conversation_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("AI conversation not found")
        return self.get_conversation(conversation_id)

    @staticmethod
    def _decode_conversation(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["pinned"] = bool(result.get("pinned"))
        result["archived"] = bool(result.get("archived"))
        result["project_id"] = result.get("project_id") or ""
        result["project_name"] = result.get("project_name") or ""
        result["message_count"] = int(result.get("message_count") or 0)
        result["last_message"] = result.get("last_message") or ""
        return result

    def add_message(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        status: str = "complete",
        provider_profile_id: str = "",
        model: str = "",
        trust_tier: str = "",
        egress_call_id: str = "",
        egress_approved: bool = False,
        retry_of_message_id: str = "",
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.get_conversation(conversation_id)
        if role not in {"user", "assistant", "system"}:
            raise ValueError("Message role must be user, assistant, or system")
        message_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_messages (
                    id, conversation_id, role, content, status,
                    provider_profile_id, model, trust_tier, egress_call_id,
                    egress_approved, retry_of_message_id, attachments_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    status,
                    provider_profile_id,
                    model,
                    trust_tier,
                    egress_call_id,
                    int(egress_approved),
                    retry_of_message_id,
                    _json(attachments or []),
                    now,
                    now,
                ),
            )
            conn.execute(
                "UPDATE off_ai_conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return self.get_message(message_id)

    def get_message(self, message_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM off_ai_messages WHERE id = ?", (message_id,))
        if not row:
            raise KeyError("AI message not found")
        return self._decode_message(row)

    def list_messages(
        self, conversation_id: str, *, limit: int = 500, before: str = ""
    ) -> list[dict[str, Any]]:
        self.get_conversation(conversation_id)
        where = ["conversation_id = ?"]
        params: list[Any] = [conversation_id]
        if before:
            where.append("created_at < ?")
            params.append(before)
        rows = self._rows(
            f"""
            SELECT * FROM off_ai_messages
            WHERE {' AND '.join(where)}
            ORDER BY created_at, id
            LIMIT ?
            """,
            (*params, limit),
        )
        return [self._decode_message(row) for row in rows]

    def approved_context_messages(
        self, conversation_id: str, *, limit: int = 12
    ) -> list[dict[str, Any]]:
        rows = self._rows(
            """
            SELECT * FROM (
                SELECT * FROM off_ai_messages
                WHERE conversation_id = ?
                  AND egress_approved = 1
                  AND status = 'complete'
                  AND role IN ('user', 'assistant')
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            ) ordered
            ORDER BY created_at, id
            """,
            (conversation_id, limit),
        )
        return [self._decode_message(row) for row in rows]

    def update_message(self, message_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "content",
            "status",
            "provider_profile_id",
            "model",
            "trust_tier",
            "egress_call_id",
            "egress_approved",
        }
        values = {key: value for key, value in changes.items() if key in allowed}
        if not values:
            return self.get_message(message_id)
        if "egress_approved" in values:
            values["egress_approved"] = int(bool(values["egress_approved"]))
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE off_ai_messages SET {assignments}, updated_at = ? WHERE id = ?",
                (*values.values(), to_utc_iso(), message_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("AI message not found")
        return self.get_message(message_id)

    @staticmethod
    def _decode_message(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["egress_approved"] = bool(result.get("egress_approved"))
        result["attachments"] = _loads(result.pop("attachments_json", "[]"), [])
        return result

    # Deterministic runtime state

    def get_context(
        self, scope_type: str, scope_id: str, *, create: bool = False
    ) -> dict[str, Any]:
        row = self._row(
            """
            SELECT * FROM off_ai_context_state
            WHERE scope_type = ? AND scope_id = ?
            """,
            (scope_type, scope_id),
        )
        if not row and create:
            now = to_utc_iso()
            with self.transaction() as conn:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO off_ai_context_state (
                        scope_type, scope_id, updated_at
                    ) VALUES (?, ?, ?)
                    """,
                    (scope_type, scope_id, now),
                )
            row = self._row(
                """
                SELECT * FROM off_ai_context_state
                WHERE scope_type = ? AND scope_id = ?
                """,
                (scope_type, scope_id),
            )
        if not row:
            raise KeyError("OFF_AI context state not found")
        return self._decode_context(row)

    def update_context(
        self, scope_type: str, scope_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        current = self.get_context(scope_type, scope_id, create=True)
        json_fields = {
            "plan",
            "done",
            "pending",
            "decisions",
            "working_drafts",
            "entity_facts",
        }
        values: dict[str, Any] = {}
        for key, value in changes.items():
            if key in {"current_task", "rolling_summary"}:
                values[key] = str(value)
            elif key in json_fields:
                values[f"{key}_json"] = _json(value)
        if not values:
            return current
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            conn.execute(
                f"""
                UPDATE off_ai_context_state
                SET {assignments}, revision = revision + 1, updated_at = ?
                WHERE scope_type = ? AND scope_id = ?
                """,
                (*values.values(), to_utc_iso(), scope_type, scope_id),
            )
        return self.get_context(scope_type, scope_id)

    def append_context_event(
        self, conversation_id: str, *, role: str, content: str
    ) -> dict[str, Any]:
        current = self.get_context("conversation", conversation_id, create=True)
        clean = " ".join(content.split())
        entry = f"{role.title()}: {clean[:360]}"
        summary = "\n".join(
            item for item in [current.get("rolling_summary", ""), entry] if item
        )
        if len(summary) > 4000:
            summary = summary[-4000:].lstrip()
        changes: dict[str, Any] = {"rolling_summary": summary}
        if role == "user":
            changes["current_task"] = clean[:1000]
        return self.update_context("conversation", conversation_id, changes)

    @staticmethod
    def _decode_context(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key, fallback in (
            ("plan", []),
            ("done", []),
            ("pending", []),
            ("decisions", []),
            ("working_drafts", []),
            ("entity_facts", {}),
        ):
            result[key] = _loads(result.pop(f"{key}_json", ""), fallback)
        result["revision"] = int(result.get("revision") or 1)
        return result

    # Attachments and deterministic intake jobs

    def create_attachment(
        self,
        *,
        conversation_id: str,
        original_name: str,
        media_type: str,
        size_bytes: int,
        sha256: str,
        storage_path: str,
        purpose: str = "campaign_intake",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if conversation_id:
            self.get_conversation(conversation_id)
        attachment_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_attachments (
                    id, conversation_id, original_name, media_type, size_bytes,
                    sha256, storage_path, purpose, metadata_json, created_at
                ) VALUES (?, NULLIF(?, ''), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    conversation_id,
                    original_name,
                    media_type,
                    int(size_bytes),
                    sha256,
                    storage_path,
                    purpose,
                    _json(metadata or {}),
                    to_utc_iso(),
                ),
            )
        return self.get_attachment(attachment_id)

    def get_attachment(self, attachment_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM off_ai_attachments WHERE id = ?", (attachment_id,))
        if not row:
            raise KeyError("AI attachment not found")
        result = dict(row)
        result["metadata"] = _loads(result.pop("metadata_json", "{}"), {})
        return result

    def create_import_job(
        self,
        *,
        attachment_id: str,
        conversation_id: str = "",
        template_text: str = "",
        public_positioning: str = "",
    ) -> dict[str, Any]:
        self.get_attachment(attachment_id)
        job_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_import_jobs (
                    id, attachment_id, conversation_id, template_text,
                    public_positioning, created_at, updated_at
                ) VALUES (?, ?, NULLIF(?, ''), ?, ?, ?, ?)
                """,
                (
                    job_id,
                    attachment_id,
                    conversation_id,
                    template_text,
                    public_positioning,
                    now,
                    now,
                ),
            )
        return self.get_import_job(job_id, private=True)

    def update_import_job(self, job_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "detected_mode",
            "selected_mode",
            "status",
            "ambiguous",
            "template_text",
            "public_positioning",
            "mapping",
            "private_result",
            "public_preview",
            "campaign_id",
            "error",
        }
        values: dict[str, Any] = {}
        for key, value in changes.items():
            if key not in allowed:
                continue
            if key in {"mapping", "private_result", "public_preview"}:
                values[f"{key}_json"] = _json(value)
            elif key == "ambiguous":
                values[key] = int(bool(value))
            else:
                values[key] = value
        if not values:
            return self.get_import_job(job_id, private=True)
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"""
                UPDATE off_ai_import_jobs
                SET {assignments}, updated_at = ?
                WHERE id = ?
                """,
                (*values.values(), to_utc_iso(), job_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Campaign intake job not found")
        return self.get_import_job(job_id, private=True)

    def get_import_job(self, job_id: str, *, private: bool = False) -> dict[str, Any]:
        row = self._row(
            """
            SELECT j.*, a.original_name, a.media_type, a.size_bytes, a.sha256
            FROM off_ai_import_jobs j
            JOIN off_ai_attachments a ON a.id = j.attachment_id
            WHERE j.id = ?
            """,
            (job_id,),
        )
        if not row:
            raise KeyError("Campaign intake job not found")
        result = dict(row)
        result["ambiguous"] = bool(result.get("ambiguous"))
        result["mapping"] = _loads(result.pop("mapping_json", "{}"), {})
        result["public_preview"] = _loads(result.pop("public_preview_json", "{}"), {})
        private_result = _loads(result.pop("private_result_json", "{}"), {})
        if private:
            result["private_result"] = private_result
        return result

    # Egress audit and quota accounting

    def begin_egress(
        self,
        *,
        conversation_id: str = "",
        message_id: str = "",
        profile: dict[str, Any],
        task_type: str,
        data_class: str,
        payload: dict[str, Any],
        status: str = "pending",
        blocked_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        call_id = str(uuid.uuid4())
        payload_json = _json(payload)
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_egress_calls (
                    id, conversation_id, message_id, provider_profile_id,
                    provider_type, model, host_origin, model_origin,
                    jurisdiction, retention_policy, trust_tier, task_type,
                    data_class, payload_json, payload_sha256, status,
                    blocked_reasons_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    conversation_id,
                    message_id,
                    str(profile.get("id", "")),
                    str(profile.get("provider_type", "")),
                    str(profile.get("model", "")),
                    str(profile.get("host_origin", "")),
                    str(profile.get("model_origin", "")),
                    str(profile.get("jurisdiction", "Unknown")),
                    str(profile.get("retention_policy", "unknown")),
                    str(profile.get("trust_tier", "D")),
                    task_type,
                    data_class,
                    payload_json,
                    hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
                    status,
                    _json(blocked_reasons or []),
                    to_utc_iso(),
                ),
            )
        return self.get_egress(call_id)

    def finish_egress(
        self,
        call_id: str,
        *,
        status: str,
        response_text: str = "",
        error: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost: float = 0,
        duration_ms: int = 0,
        blocked_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE off_ai_egress_calls
                SET status = ?, response_text = ?, error = ?,
                    input_tokens = ?, output_tokens = ?, estimated_cost = ?,
                    duration_ms = ?, blocked_reasons_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    response_text,
                    error[:2000],
                    int(input_tokens),
                    int(output_tokens),
                    float(estimated_cost),
                    int(duration_ms),
                    _json(blocked_reasons or []),
                    to_utc_iso(),
                    call_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError("Egress audit record not found")
        return self.get_egress(call_id)

    def get_egress(self, call_id: str) -> dict[str, Any]:
        row = self._row("SELECT * FROM off_ai_egress_calls WHERE id = ?", (call_id,))
        if not row:
            raise KeyError("Egress audit record not found")
        return self._decode_egress(row)

    def list_egress(
        self,
        *,
        status: str = "",
        profile_id: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1 = 1"]
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if profile_id:
            where.append("provider_profile_id = ?")
            params.append(profile_id)
        clause = " AND ".join(where)
        count = self._row(
            f"SELECT COUNT(*) AS count FROM off_ai_egress_calls WHERE {clause}", params
        )
        rows = self._rows(
            f"""
            SELECT * FROM off_ai_egress_calls
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [self._decode_egress(row) for row in rows], int(
            count["count"] if count else 0
        )

    @staticmethod
    def _decode_egress(row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        result["payload"] = _loads(result.pop("payload_json", "{}"), {})
        result["blocked_reasons"] = _loads(
            result.pop("blocked_reasons_json", "[]"), []
        )
        result["input_tokens"] = int(result.get("input_tokens") or 0)
        result["output_tokens"] = int(result.get("output_tokens") or 0)
        result["duration_ms"] = int(result.get("duration_ms") or 0)
        result["estimated_cost"] = float(result.get("estimated_cost") or 0)
        return result

    def record_usage(
        self,
        profile_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
        when: datetime | None = None,
    ) -> None:
        now = when or datetime.now(timezone.utc)
        usage_date = now.date().isoformat()
        with self.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO off_ai_provider_usage (
                    profile_id, usage_date, requests, input_tokens,
                    output_tokens, estimated_cost, updated_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(profile_id, usage_date) DO UPDATE SET
                    requests = requests + 1,
                    input_tokens = input_tokens + excluded.input_tokens,
                    output_tokens = output_tokens + excluded.output_tokens,
                    estimated_cost = estimated_cost + excluded.estimated_cost,
                    updated_at = excluded.updated_at
                """,
                (
                    profile_id,
                    usage_date,
                    int(input_tokens),
                    int(output_tokens),
                    float(estimated_cost),
                    to_utc_iso(now),
                ),
            )

    def usage_for_profile(
        self, profile_id: str, *, today: date | None = None
    ) -> dict[str, Any]:
        today = today or datetime.now(timezone.utc).date()
        day = self._row(
            """
            SELECT * FROM off_ai_provider_usage
            WHERE profile_id = ? AND usage_date = ?
            """,
            (profile_id, today.isoformat()),
        ) or {}
        month_prefix = today.strftime("%Y-%m") + "-%"
        month = self._row(
            """
            SELECT COALESCE(SUM(requests), 0) AS requests,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   COALESCE(SUM(estimated_cost), 0) AS estimated_cost
            FROM off_ai_provider_usage
            WHERE profile_id = ? AND usage_date LIKE ?
            """,
            (profile_id, month_prefix),
        ) or {}
        recent_minute = self._row(
            """
            SELECT COUNT(*) AS requests
            FROM off_ai_egress_calls
            WHERE provider_profile_id = ?
              AND status IN ('pending', 'succeeded', 'failed')
              AND julianday(created_at) >= julianday('now', '-1 minute')
            """,
            (profile_id,),
        ) or {}
        return {
            "profile_id": profile_id,
            "today": {
                "requests": int(day.get("requests") or 0),
                "input_tokens": int(day.get("input_tokens") or 0),
                "output_tokens": int(day.get("output_tokens") or 0),
                "estimated_cost": float(day.get("estimated_cost") or 0),
            },
            "month": {
                "requests": int(month.get("requests") or 0),
                "input_tokens": int(month.get("input_tokens") or 0),
                "output_tokens": int(month.get("output_tokens") or 0),
                "estimated_cost": float(month.get("estimated_cost") or 0),
            },
            "last_minute_requests": int(recent_minute.get("requests") or 0),
        }

    # Human-readable notebook record and feedback recommendations

    def add_activity(
        self,
        *,
        record_type: str,
        event_type: str,
        payload: dict[str, Any],
        project_id: str = "",
        conversation_id: str = "",
        campaign_id: str = "",
        contact_token: str = "",
        variant_id: str = "",
    ) -> dict[str, Any]:
        record_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_activity_records (
                    id, record_type, project_id, conversation_id, campaign_id,
                    contact_token, variant_id, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record_type,
                    project_id,
                    conversation_id,
                    campaign_id,
                    contact_token,
                    variant_id,
                    event_type,
                    _json(payload),
                    now,
                ),
            )
        result = self._row(
            "SELECT * FROM off_ai_activity_records WHERE id = ?", (record_id,)
        ) or {}
        result["payload"] = _loads(result.pop("payload_json", "{}"), {})
        return result

    def create_template_recommendation(
        self,
        *,
        template_id: str,
        variant_id: str,
        sample_size: int,
        reply_rate: float,
        current_template: str,
        suggested_template: str,
        egress_call_id: str,
    ) -> dict[str, Any]:
        recommendation_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO off_ai_template_recommendations (
                    id, template_id, variant_id, sample_size, reply_rate,
                    current_template, suggested_template, egress_call_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    template_id,
                    variant_id,
                    int(sample_size),
                    float(reply_rate),
                    current_template,
                    suggested_template,
                    egress_call_id,
                    to_utc_iso(),
                ),
            )
        return self.get_template_recommendation(recommendation_id)

    def get_template_recommendation(self, recommendation_id: str) -> dict[str, Any]:
        row = self._row(
            "SELECT * FROM off_ai_template_recommendations WHERE id = ?",
            (recommendation_id,),
        )
        if not row:
            raise KeyError("Template recommendation not found")
        return row

    def list_template_recommendations(
        self, *, status: str = "", limit: int = 100, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1 = 1"]
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        clause = " AND ".join(where)
        total = self._row(
            f"SELECT COUNT(*) AS count FROM off_ai_template_recommendations WHERE {clause}",
            params,
        )
        rows = self._rows(
            f"""
            SELECT * FROM off_ai_template_recommendations
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return rows, int((total or {}).get("count") or 0)

    def review_template_recommendation(
        self, recommendation_id: str, *, approved: bool
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE off_ai_template_recommendations
                SET status = ?, reviewed_at = ?
                WHERE id = ? AND status = 'pending_review'
                """,
                (
                    "approved" if approved else "rejected",
                    to_utc_iso(),
                    recommendation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Recommendation is missing or already reviewed")
        return self.get_template_recommendation(recommendation_id)

    def stats(self) -> dict[str, int]:
        queries = {
            "projects": "SELECT COUNT(*) AS count FROM off_ai_projects WHERE archived = 0",
            "conversations": "SELECT COUNT(*) AS count FROM off_ai_conversations WHERE archived = 0",
            "messages": "SELECT COUNT(*) AS count FROM off_ai_messages",
            "imports": "SELECT COUNT(*) AS count FROM off_ai_import_jobs",
            "egress_calls": "SELECT COUNT(*) AS count FROM off_ai_egress_calls",
            "blocked_calls": "SELECT COUNT(*) AS count FROM off_ai_egress_calls WHERE status = 'blocked'",
        }
        return {
            key: int((self._row(query) or {}).get("count") or 0)
            for key, query in queries.items()
        }
