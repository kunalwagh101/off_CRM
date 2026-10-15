"""Campaign-scoped sales conversion, relationship summary, and daily work queue.

All actions are local database operations. Nothing invokes an email provider,
changes an email approval, or sends/queues a message.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .models import to_utc_iso, utc_now
from .sales import SalesTracker
from .store import OutreachStore


_ELIGIBLE_OUTCOMES = frozenset({"positive", "meeting"})


class RelationshipOperations:
    def __init__(self, store: OutreachStore, sales: SalesTracker) -> None:
        self.store = store
        self.sales = sales

    def _sales_link(self, campaign_id: str, membership_id: str) -> dict[str, Any] | None:
        return self.store._row(
            """SELECT l.id, l.lead_name, l.company, l.email, l.lead_status, l.revision,
                      x.linked_at
               FROM campaign_sales_links x
               JOIN campaign_contacts cc ON cc.id = x.campaign_contact_id
               JOIN sales_leads l ON l.id = x.sales_lead_id
               WHERE cc.campaign_id = ? AND cc.id = ? AND l.workspace_id = ?""",
            (campaign_id, membership_id, self.sales.workspace_id),
        )

    def promote_reply(self, campaign_id: str, membership_id: str) -> dict[str, Any]:
        """Only a human-triaged qualified reply can become a lead.

        A saved membership->lead link is the idempotency key. A same-workspace
        lead with an existing email is reused, without overwriting fields.
        All lookup, creation, and linking occur in one write transaction.
        """
        with self.store.transaction(immediate=True) as conn:
            contact = self.store.get_campaign_contact(campaign_id, membership_id)
            linked = self._sales_link(campaign_id, membership_id)
            if linked:
                return {"lead": linked, "created": False, "linked": False}
            triage = self.store._row(
                """SELECT review_status, outcome FROM campaign_reply_triage
                   WHERE campaign_contact_id = ?""", (membership_id,),
            )
            if not triage or triage["review_status"] != "triaged" or triage["outcome"] not in _ELIGIBLE_OUTCOMES:
                raise ValueError("Mark a received reply as reviewed and Positive or Meeting before conversion")
            has_reply = self.store._row(
                """SELECT id FROM messages WHERE campaign_contact_id = ?
                   AND direction = 'inbound' LIMIT 1""", (membership_id,),
            )
            if not has_reply:
                raise ValueError("A stored incoming reply is required")
            email = str(contact["email"] or "").strip().lower()
            if not email:
                raise ValueError("Contact has no email for safe lead reconciliation")
            candidates = self.store._rows(
                """SELECT id FROM sales_leads WHERE workspace_id = ?
                   AND lower(email) = ? ORDER BY created_at, id LIMIT 2""",
                (self.sales.workspace_id, email),
            )
            if len(candidates) > 1:
                raise ValueError("Multiple existing sales leads match this email; resolve them in Sales Tracker first")
            created = not candidates
            if candidates:
                lead_id = str(candidates[0]["id"])
            else:
                lead = self.sales.create_lead({
                    "lead_name": contact["full_name"], "email": email,
                    "company": contact["company"],
                    "source": "Campaign reply",
                    "lead_status": "new",
                })
                lead_id = str(lead["id"])
            conn.execute(
                """INSERT INTO campaign_sales_links
                   (campaign_contact_id, sales_lead_id, linked_at)
                   VALUES (?, ?, ?)""",
                (membership_id, lead_id, to_utc_iso()),
            )
            self.store.add_event(
                campaign_id, "reply_converted_to_sales",
                {"lead_id": lead_id, "created": created},
                campaign_contact_id=membership_id,
            )
        link = self._sales_link(campaign_id, membership_id)
        assert link is not None
        return {"lead": link, "created": created, "linked": True}

    def contact_360(self, campaign_id: str, membership_id: str) -> dict[str, Any]:
        contact = self.store.get_campaign_contact(campaign_id, membership_id)
        # Explicit allowlists: neither the contact's private notes nor original
        # raw-provider JSON are returned in this concise overview.
        identity = {k: contact.get(k) for k in (
            "id", "full_name", "email", "company", "title", "category", "status",
            "current_stage", "variant_id", "recipient_timezone",
        )}
        totals = self.store._row(
            """SELECT SUM(CASE WHEN direction='outbound' THEN 1 ELSE 0 END) AS sent,
                      SUM(CASE WHEN direction='inbound' THEN 1 ELSE 0 END) AS received
               FROM messages WHERE campaign_contact_id = ?""",
            (membership_id,),
        ) or {}
        reply = self.store._row(
            """SELECT id, SUBSTR(subject, 1, 200) AS subject,
                      COALESCE(received_at, created_at) AS received_at
               FROM messages WHERE campaign_contact_id = ? AND direction='inbound'
               ORDER BY COALESCE(received_at, created_at) DESC, id DESC LIMIT 1""",
            (membership_id,),
        )
        triage = self.store._row(
            """SELECT review_status, outcome, updated_at
               FROM campaign_reply_triage WHERE campaign_contact_id = ?""",
            (membership_id,),
        )
        tasks = self.store._row(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open
               FROM campaign_followup_tasks
               WHERE campaign_id = ? AND campaign_contact_id = ?""",
            (campaign_id, membership_id),
        ) or {}
        next_task = self.store._row(
            """SELECT id, title, due_at, priority, assigned_to
               FROM campaign_followup_tasks
               WHERE campaign_id = ? AND campaign_contact_id = ? AND status='open'
               ORDER BY due_at ASC, id ASC LIMIT 1""",
            (campaign_id, membership_id),
        )
        return {
            "campaign_id": campaign_id,
            "contact": identity,
            "messages": {"sent": int(totals.get("sent") or 0),
                         "received": int(totals.get("received") or 0)},
            "latest_reply": reply,
            "triage": triage or {"review_status": "unreviewed", "outcome": ""},
            "tasks": {"total": int(tasks.get("total") or 0),
                      "open": int(tasks.get("open") or 0),
                      "next": next_task},
            "sales_lead": self._sales_link(campaign_id, membership_id),
        }

    def action_center(
        self, campaign_id: str, *, now: datetime | None = None,
        action_type: str = "all", limit: int = 50, offset: int = 0,
    ) -> dict[str, Any]:
        self.store.get_campaign(campaign_id)
        if action_type not in {"all", "overdue_task", "reply_review", "sales_attention"}:
            raise ValueError("Invalid action type")
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid action page")
        moment = now or utc_now()
        overdue = moment.astimezone(timezone.utc).isoformat()
        cutoff = (moment - timedelta(days=7)).astimezone(timezone.utc).isoformat()
        # All three sources expose the same safe, bounded list projection.
        # Database filtering/paging avoids fetching every private message.
        source = """
            SELECT 'overdue_task' AS action_type, 0 AS sort_group,
                   t.id AS item_id, t.campaign_contact_id,
                   NULL AS sales_lead_id, t.title AS headline,
                   t.due_at AS occurred_at, t.due_at AS due_at,
                   t.priority AS priority,
                   'Overdue human follow-up' AS reason
            FROM campaign_followup_tasks t
            WHERE t.campaign_id = ? AND t.status = 'open' AND t.due_at < ?
            UNION ALL
            SELECT 'reply_review', 1, m.id, cc.id, NULL,
                   c.full_name, COALESCE(m.received_at, m.created_at),
                   NULL, 'normal', 'Incoming reply needs review'
            FROM campaign_contacts cc
            JOIN contacts c ON c.id = cc.contact_id
            JOIN messages m ON m.id = (
                SELECT im.id FROM messages im
                WHERE im.campaign_contact_id = cc.id AND im.direction = 'inbound'
                ORDER BY COALESCE(im.received_at, im.created_at) DESC, im.id DESC LIMIT 1
            )
            LEFT JOIN campaign_reply_triage rt ON rt.campaign_contact_id = cc.id
            WHERE cc.campaign_id = ?
              AND COALESCE(rt.review_status, 'unreviewed') = 'unreviewed'
            UNION ALL
            SELECT 'sales_attention', 2, l.id, MIN(cc.id), l.id,
                   l.lead_name, COALESCE(l.last_touch_at, MIN(x.linked_at)),
                   NULL, 'normal',
                   CASE WHEN l.last_touch_at IS NULL THEN 'No recorded sales touch'
                        ELSE 'No sales touch in the past seven days' END
            FROM campaign_sales_links x
            JOIN campaign_contacts cc ON cc.id = x.campaign_contact_id
            JOIN sales_leads l ON l.id = x.sales_lead_id
            WHERE cc.campaign_id = ? AND l.workspace_id = ?
              AND l.lead_status NOT IN ('won', 'lost')
              AND (l.last_touch_at IS NULL OR l.last_touch_at < ?)
            GROUP BY l.id, l.lead_name, l.last_touch_at
        """
        params: list[Any] = [
            campaign_id, overdue, campaign_id,
            campaign_id, self.sales.workspace_id, cutoff,
        ]
        clause = ""
        if action_type != "all":
            clause = "WHERE action_type = ?"
            params.append(action_type)
        cte = "WITH actions AS (" + source + ")"
        counts = self.store._rows(
            cte + " SELECT action_type, COUNT(*) AS total FROM actions "
                  "GROUP BY action_type", params[:6],
        )
        counts_by_type = {k: 0 for k in ("overdue_task", "reply_review", "sales_attention")}
        counts_by_type.update({str(r["action_type"]): int(r["total"]) for r in counts})
        rows = self.store._rows(
            cte + " SELECT action_type, item_id, campaign_contact_id, sales_lead_id,"
                  " headline, occurred_at, due_at, priority, reason FROM actions "
                  + clause
                  + " ORDER BY sort_group ASC, occurred_at ASC, item_id ASC "
                    "LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )
        return {
            "items": rows, "total": (
                sum(counts_by_type.values()) if action_type == "all"
                else counts_by_type[action_type]
            ),
            "counts": counts_by_type, "limit": limit, "offset": offset,
            "evaluated_at": overdue,
            "sales_attention_rule": "No touch recorded, or last touch more than seven days ago",
        }
