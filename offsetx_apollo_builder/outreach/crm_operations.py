"""Read-only CRM quality, campaign comparison and human task reporting.

Derived from saved CRM records only. Never sends messages or calls an AI model.
CRM scope remains install-wide pending owner decision Q-27.
"""
from __future__ import annotations

from typing import Any

from .models import clean_text, to_utc_iso
from .sales import SalesTracker
from .store import OutreachStore


class CRMOperations:
    def __init__(self, store: OutreachStore, sales: SalesTracker) -> None:
        self.store = store
        self.sales = sales

    @staticmethod
    def _page(limit: int, offset: int) -> None:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Page limit must be 1–100 and offset nonnegative")

    def contact_quality(
        self, *, issue: str = "all", search: str = "",
        limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """Surface review candidates, never automatically alter identities."""
        self._page(limit, offset)
        term = clean_text(search).strip()
        if len(term) > 100:
            raise ValueError("Contact search must not exceed 100 characters")
        flags = {
            "missing_email": "trim(c.email) = ''",
            "missing_company": "trim(c.company) = ''",
            "missing_title": "trim(c.title) = ''",
            "not_in_campaign": "NOT EXISTS (SELECT 1 FROM campaign_contacts cc WHERE cc.contact_id = c.id)",
            "sales_overlap": """trim(c.email) <> '' AND EXISTS (
                SELECT 1 FROM sales_leads l WHERE l.workspace_id = ?
                  AND lower(trim(l.email)) = lower(trim(c.email)))""",
        }
        if issue not in {*flags, "all"}:
            raise ValueError("Choose a supported data-quality category")
        # The only dynamic SQL is from this hardcoded condition allowlist.
        overlap = flags["sales_overlap"]
        if issue == "all":
            condition = "(" + " OR ".join("(" + value + ")" for value in flags.values()) + ")"
            where_args: list[Any] = [self.sales.workspace_id]
        else:
            condition = flags[issue]
            where_args = [self.sales.workspace_id] if issue == "sales_overlap" else []
        if term:
            condition += """ AND (lower(c.full_name) LIKE lower(?) ESCAPE '\\'
                OR lower(c.email) LIKE lower(?) ESCAPE '\\'
                OR lower(c.company) LIKE lower(?) ESCAPE '\\')"""
            pattern = self.store._like(term)
            where_args.extend([pattern, pattern, pattern])
        total = self.store._row(
            "SELECT COUNT(*) AS count FROM contacts c WHERE " + condition, tuple(where_args),
        )
        rows = self.store._rows(
            """SELECT c.id, c.full_name, c.email, c.company, c.title,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.contact_id = c.id) AS campaign_count,
                   (SELECT cc.campaign_id FROM campaign_contacts cc
                    WHERE cc.contact_id = c.id ORDER BY cc.created_at, cc.id LIMIT 1)
                    AS campaign_id,
                   (SELECT cc.id FROM campaign_contacts cc
                    WHERE cc.contact_id = c.id ORDER BY cc.created_at, cc.id LIMIT 1)
                    AS campaign_contact_id,
                   CASE WHEN """ + overlap + """ THEN 1 ELSE 0 END AS sales_overlap
               FROM contacts c WHERE """ + condition +
            " ORDER BY lower(c.full_name), c.id LIMIT ? OFFSET ?",
            (self.sales.workspace_id, *where_args, limit, offset),
        )
        for row in rows:
            labels = []
            if not row["email"].strip():
                labels.append("missing_email")
            if not row["company"].strip():
                labels.append("missing_company")
            if not row["title"].strip():
                labels.append("missing_title")
            if int(row["campaign_count"]) == 0:
                labels.append("not_in_campaign")
            if row.pop("sales_overlap"):
                labels.append("sales_overlap")
            row["issues"] = labels
        return {
            "items": rows, "total": int(total["count"] or 0),
            "limit": limit, "offset": offset, "issue": issue, "search": term,
            "identity_note": "A matching email in Sales Tracker is a review hint, not proof of a duplicate.",
        }

    def campaign_comparison(
        self, *, search: str = "", limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """Count unique membership outcomes, not raw reply-message duplicates."""
        self._page(limit, offset)
        term = clean_text(search).strip()
        if len(term) > 100:
            raise ValueError("Campaign search must not exceed 100 characters")
        where = """WHERE lower(ca.name) LIKE lower(?) ESCAPE '\\'""" if term else ""
        args: list[Any] = [self.store._like(term)] if term else []
        total = self.store._row(
            "SELECT COUNT(*) AS count FROM campaigns ca " + where, tuple(args),
        )
        rows = self.store._rows(
            """SELECT ca.id AS campaign_id, ca.name AS campaign_name,
                      ca.kind, ca.status,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = ca.id) AS contacts,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = ca.id AND EXISTS (
                        SELECT 1 FROM messages m
                        WHERE m.campaign_contact_id = cc.id AND m.direction = 'outbound'
                   )) AS contacted,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = ca.id AND EXISTS (
                        SELECT 1 FROM messages m WHERE m.campaign_contact_id = cc.id
                          AND m.direction = 'outbound'
                   ) AND EXISTS (
                        SELECT 1 FROM messages m WHERE m.campaign_contact_id = cc.id
                          AND m.direction = 'inbound'
                   )) AS replied_after_outreach,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    WHERE cc.campaign_id = ca.id AND EXISTS (
                        SELECT 1 FROM messages m WHERE m.campaign_contact_id = cc.id
                          AND m.direction = 'inbound'
                   )) AS inbound_contacts,
                   (SELECT COUNT(*) FROM campaign_contacts cc
                    JOIN campaign_reply_triage rt ON rt.campaign_contact_id = cc.id
                    WHERE cc.campaign_id = ca.id AND rt.review_status = 'triaged'
                      AND rt.outcome IN ('positive', 'meeting')) AS qualified,
                   (SELECT COUNT(*) FROM campaign_sales_links x
                    JOIN campaign_contacts cc ON cc.id = x.campaign_contact_id
                    WHERE cc.campaign_id = ca.id) AS sales_links
               FROM campaigns ca """ + where +
            " ORDER BY lower(ca.name), ca.id LIMIT ? OFFSET ?",
            (*args, limit, offset),
        )
        for row in rows:
            row["reply_rate_percent"] = round(
                100 * int(row["replied_after_outreach"]) / int(row["contacted"]), 1
            ) if row["contacted"] else None
        return {
            "items": rows, "total": int(total["count"] or 0),
            "limit": limit, "offset": offset, "search": term,
            "rate_note": "Reply rate uses contacts with saved outbound messages as denominator; only those with both outbound and inbound count as replies. No statistical adjustment.",
            "sales_note": "Sales links are membership associations, not unique attributed revenue or causal proof.",
        }

    def followup_performance(
        self, *, campaign_id: str = "", limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """Group by display owner label, not an identity/permission principal."""
        self._page(limit, offset)
        if campaign_id:
            self.store.get_campaign(campaign_id)
        where = "WHERE t.campaign_id = ?" if campaign_id else ""
        where_args: list[Any] = [campaign_id] if campaign_id else []
        now = to_utc_iso()
        source = """FROM campaign_followup_tasks t """ + where
        summary = self.store._row(
            """SELECT COUNT(*) AS tasks,
                   COALESCE(SUM(CASE WHEN t.status = 'open' THEN 1 ELSE 0 END),0) AS open,
                   COALESCE(SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END),0) AS done,
                   COALESCE(SUM(CASE WHEN t.status = 'open' AND t.due_at < ?
                        THEN 1 ELSE 0 END),0) AS overdue,
                   COALESCE(SUM(CASE WHEN t.status = 'done' AND t.completed_at IS NOT NULL
                        AND t.completed_at <= t.due_at THEN 1 ELSE 0 END),0) AS on_time
               """ + source,
            (now, *where_args),
        ) or {}
        owners = """WITH groups AS (
            SELECT lower(trim(t.assigned_to)) AS owner_key,
                   CASE WHEN MIN(trim(t.assigned_to)) = '' THEN 'Unassigned'
                        ELSE MIN(trim(t.assigned_to)) END AS owner,
                   COUNT(*) AS tasks,
                   SUM(CASE WHEN t.status = 'open' THEN 1 ELSE 0 END) AS open,
                   SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN t.status = 'open' AND t.due_at < ? THEN 1 ELSE 0 END) AS overdue,
                   SUM(CASE WHEN t.status = 'done' AND t.completed_at IS NOT NULL
                         AND t.completed_at <= t.due_at THEN 1 ELSE 0 END) AS on_time
            """ + source + """
            GROUP BY lower(trim(t.assigned_to))
        )"""
        total = self.store._row(
            owners + " SELECT COUNT(*) AS count FROM groups", (now, *where_args),
        )
        rows = self.store._rows(
            owners + """ SELECT owner_key, owner, tasks, open, done, overdue, on_time
                FROM groups ORDER BY lower(owner), owner_key LIMIT ? OFFSET ?""",
            (now, *where_args, limit, offset),
        )
        return {
            "items": rows, "total": int(total["count"] or 0),
            "overall": {key: int(summary.get(key) or 0) for key in
                        ("tasks", "open", "done", "overdue", "on_time")},
            "limit": limit, "offset": offset, "campaign_id": campaign_id,
            "owner_note": "Owner names are free-text labels, not verified user identities or permissions. On-time compares saved completion time with due time.",
        }
