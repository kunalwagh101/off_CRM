"""Campaign-scoped reply triage, correspondence and human follow-up tasks.

No external provider calls and no automatic outbound effects. These operations
read or update only campaign-scoped records through the existing CRM store.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .models import to_utc_iso
from .store import OutreachStore


class TaskConflictError(ValueError):
    """A colleague changed the task since the browser last read it."""


class CampaignRelationships:
    def __init__(self, store: OutreachStore) -> None:
        self.store = store

    def inbox(
        self, campaign_id: str, *, limit: int = 50, offset: int = 0,
        review_status: str = "all", outcome: str = "",
    ) -> dict[str, Any]:
        self.store.get_campaign(campaign_id)
        if review_status not in {"all", "unreviewed", "triaged"}:
            raise ValueError("Invalid reply review status")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid reply page")
        where = ["cc.campaign_id = ?"]
        params: list[Any] = [campaign_id]
        if review_status != "all":
            where.append("COALESCE(rt.review_status, 'unreviewed') = ?")
            params.append(review_status)
        if outcome:
            where.append("COALESCE(rt.outcome, '') = ?")
            params.append(outcome)
        clause = " AND ".join(where)
        joined = """FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id
            JOIN messages m ON m.id = (
                SELECT im.id FROM messages im
                WHERE im.campaign_contact_id = cc.id AND im.direction = 'inbound'
                ORDER BY COALESCE(im.received_at, im.created_at) DESC, im.id DESC LIMIT 1
            )
            LEFT JOIN campaign_reply_triage rt ON rt.campaign_contact_id = cc.id"""
        count = self.store.connection.execute(
            f"SELECT COUNT(*) AS count {joined} WHERE {clause}", params,
        ).fetchone()
        rows = self.store._rows(
            f"""SELECT cc.id AS campaign_contact_id, cc.status,
                       c.full_name, c.email, c.company,
                       m.id AS latest_message_id, SUBSTR(m.subject, 1, 300) AS subject,
                       SUBSTR(m.body, 1, 500) AS reply_preview,
                       COALESCE(m.received_at, m.created_at) AS received_at,
                       COALESCE(rt.review_status, 'unreviewed') AS review_status,
                       COALESCE(rt.outcome, '') AS outcome,
                       COALESCE(rt.note, '') AS triage_note
                {joined} WHERE {clause}
                ORDER BY COALESCE(m.received_at, m.created_at) DESC, m.id DESC
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        )
        return {"items": rows, "total": int(count["count"] if count else 0),
                "limit": limit, "offset": offset}

    def triage(
        self, campaign_id: str, membership_id: str, *,
        review_status: str, outcome: str, note: str = "",
    ) -> dict[str, Any]:
        if review_status not in {"unreviewed", "triaged"}:
            raise ValueError("Invalid review status")
        if outcome not in {"", "positive", "neutral", "negative", "meeting",
                           "not_interested", "wrong_person"}:
            raise ValueError("Invalid reply outcome")
        if len(note) > 1000:
            raise ValueError("Triage note exceeds 1,000 characters")
        with self.store.transaction(immediate=True) as conn:
            self.store.get_campaign_contact(campaign_id, membership_id)
            row = self.store._row(
                """SELECT 1 AS found FROM messages WHERE campaign_contact_id = ?
                   AND direction = 'inbound' LIMIT 1""", (membership_id,),
            )
            if row is None:
                raise ValueError("This contact has no received reply to triage")
            conn.execute(
                """INSERT INTO campaign_reply_triage
                    (campaign_contact_id, review_status, outcome, note, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(campaign_contact_id) DO UPDATE SET
                     review_status = excluded.review_status,
                     outcome = excluded.outcome,
                     note = excluded.note,
                     updated_at = excluded.updated_at""",
                (membership_id, review_status, outcome, note, to_utc_iso()),
            )
            # Do not mutate shared contacts.outcome_label here: it is global
            # across campaigns, whereas review is intentionally campaign-scoped.
            self.store.add_event(
                campaign_id, "reply_triaged",
                {"review_status": review_status, "outcome": outcome},
                campaign_contact_id=membership_id,
            )
        return {"campaign_contact_id": membership_id, "review_status": review_status,
                "outcome": outcome, "note": note}

    def conversation(
        self, campaign_id: str, membership_id: str, *,
        limit: int = 50, offset: int = 0,
    ) -> dict[str, Any]:
        contact = self.store.get_campaign_contact(campaign_id, membership_id)
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid message page")
        total = self.store.connection.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE campaign_contact_id = ?",
            (membership_id,),
        ).fetchone()
        rows = self.store._rows(
            """SELECT id, direction, stage, SUBSTR(subject, 1, 300) AS subject,
                      SUBSTR(body, 1, 2000) AS body_preview,
                      CASE WHEN LENGTH(body) > 2000 THEN 1 ELSE 0 END AS truncated,
                      sent_at, received_at, created_at
               FROM messages WHERE campaign_contact_id = ?
               ORDER BY COALESCE(received_at, sent_at, created_at) DESC, id DESC
               LIMIT ? OFFSET ?""",
            (membership_id, limit, offset),
        )
        return {
            "campaign_contact_id": membership_id,
            "contact": {"full_name": contact["full_name"],
                        "email": contact["email"], "company": contact["company"]},
            "items": rows, "total": int(total["count"] if total else 0),
            "limit": limit, "offset": offset,
        }

    def list_tasks(
        self, campaign_id: str, *, limit: int = 50, offset: int = 0,
        status: str = "open", overdue_only: bool = False,
    ) -> dict[str, Any]:
        self.store.get_campaign(campaign_id)
        if status not in {"open", "done", "all"} or not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid task filter or page")
        where = ["t.campaign_id = ?"]
        params: list[Any] = [campaign_id]
        if status != "all":
            where.append("t.status = ?")
            params.append(status)
        if overdue_only:
            where.append("t.status = 'open' AND t.due_at < ?")
            params.append(to_utc_iso())
        clause = " AND ".join(where)
        count = self.store.connection.execute(
            f"SELECT COUNT(*) AS count FROM campaign_followup_tasks t WHERE {clause}",
            params,
        ).fetchone()
        rows = self.store._rows(
            f"""SELECT t.id, t.campaign_id, t.campaign_contact_id, t.title,
                       t.description, t.assigned_to, t.due_at, t.priority,
                       t.status, t.revision, t.completed_at, t.created_at, t.updated_at,
                       COALESCE(c.full_name, '') AS contact_name,
                       COALESCE(c.email, '') AS contact_email
                FROM campaign_followup_tasks t
                LEFT JOIN campaign_contacts cc ON cc.id = t.campaign_contact_id
                LEFT JOIN contacts c ON c.id = cc.contact_id
                WHERE {clause}
                ORDER BY CASE WHEN t.status = 'open' THEN 0 ELSE 1 END,
                         t.due_at ASC, t.id ASC LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        )
        return {"items": rows, "total": int(count["count"] if count else 0),
                "limit": limit, "offset": offset}

    def _task(self, campaign_id: str, task_id: str) -> dict[str, Any]:
        row = self.store._row(
            """SELECT id, campaign_id, campaign_contact_id, title, description,
                      assigned_to, due_at, priority, status, revision, completed_at,
                      created_at, updated_at
               FROM campaign_followup_tasks WHERE campaign_id = ? AND id = ?""",
            (campaign_id, task_id),
        )
        if row is None:
            raise KeyError("Follow-up task not found in this campaign")
        return row

    def create_task(
        self, campaign_id: str, *, title: str, due_at: datetime,
        campaign_contact_id: str | None = None,
        description: str = "", assigned_to: str = "", priority: str = "normal",
    ) -> dict[str, Any]:
        name = title.strip()
        if not name or len(name) > 160 or priority not in {"normal", "high"}:
            raise ValueError("Invalid follow-up task")
        if due_at.tzinfo is None:
            raise ValueError("Due time needs an explicit timezone")
        task_id = str(uuid.uuid4())
        now = to_utc_iso()
        with self.store.transaction(immediate=True) as conn:
            self.store.get_campaign(campaign_id)
            if campaign_contact_id is not None:
                if not campaign_contact_id.strip():
                    raise ValueError("Choose a valid campaign contact or leave it empty")
                self.store.get_campaign_contact(campaign_id, campaign_contact_id)
            conn.execute(
                """INSERT INTO campaign_followup_tasks
                    (id, campaign_id, campaign_contact_id, title, description,
                     assigned_to, due_at, priority, status, revision, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', 1, ?, ?)""",
                (task_id, campaign_id, campaign_contact_id, name, description,
                 assigned_to, due_at.astimezone(timezone.utc).isoformat(),
                 priority, now, now),
            )
            self.store.add_event(
                campaign_id, "followup_task_created", {"task_id": task_id},
                campaign_contact_id=campaign_contact_id,
            )
        return self._task(campaign_id, task_id)

    def update_task(
        self, campaign_id: str, task_id: str, *,
        revision: int, status: str | None = None, title: str | None = None,
        description: str | None = None, assigned_to: str | None = None,
        due_at: datetime | None = None, priority: str | None = None,
    ) -> dict[str, Any]:
        if revision < 1:
            raise ValueError("Invalid task revision")
        if status is not None and status not in {"open", "done"}:
            raise ValueError("Invalid task status")
        if title is not None and (not title.strip() or len(title) > 160):
            raise ValueError("Invalid task title")
        if priority is not None and priority not in {"normal", "high"}:
            raise ValueError("Invalid task priority")
        if due_at is not None and due_at.tzinfo is None:
            raise ValueError("Due time needs an explicit timezone")
        changes: dict[str, Any] = {}
        for k, v in (("title", title.strip() if title is not None else None),
                     ("description", description), ("assigned_to", assigned_to),
                     ("priority", priority), ("status", status)):
            if v is not None:
                changes[k] = v
        if due_at is not None:
            changes["due_at"] = due_at.astimezone(timezone.utc).isoformat()
        with self.store.transaction(immediate=True) as conn:
            existing = self._task(campaign_id, task_id)
            if int(existing["revision"]) != revision:
                raise TaskConflictError("Task changed elsewhere. Refresh before saving.")
            if status == "done" and existing["status"] != "done":
                changes["completed_at"] = to_utc_iso()
            elif status == "open" and existing["status"] == "done":
                changes["completed_at"] = None
            if not changes:
                return existing
            changes["updated_at"] = to_utc_iso()
            assignments = ", ".join(f"{field} = ?" for field in changes)
            cursor = conn.execute(
                f"""UPDATE campaign_followup_tasks
                    SET {assignments}, revision = revision + 1
                    WHERE campaign_id = ? AND id = ? AND revision = ?""",
                (*changes.values(), campaign_id, task_id, revision),
            )
            if cursor.rowcount != 1:
                raise TaskConflictError("Task changed elsewhere. Refresh before saving.")
            self.store.add_event(
                campaign_id, "followup_task_updated",
                {"task_id": task_id, "fields": sorted(changes)},
                campaign_contact_id=existing.get("campaign_contact_id"),
            )
        return self._task(campaign_id, task_id)
