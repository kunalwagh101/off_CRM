"""Read-only CRM discovery, company intelligence and attributed sales outcomes.

Single authenticated local CRM workspace. No external network/model calls.
All output is purpose-selected: no message bodies, private notes or secrets.
"""
from __future__ import annotations

from typing import Any

from .models import clean_text
from .sales import SalesTracker
from .store import OutreachStore


class CRMInsights:
    def __init__(self, store: OutreachStore, sales: SalesTracker) -> None:
        self.store = store
        self.sales = sales

    @staticmethod
    def _page(limit: int, offset: int) -> None:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Page limit must be 1–100 and offset nonnegative")

    @staticmethod
    def _company_key(company: str) -> str:
        key = clean_text(company).strip().lower()
        if not key or len(key) > 200:
            raise ValueError("A valid company name is required")
        return key

    def search(
        self, query: str, *, kind: str = "contacts",
        limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """Search safe contact/lead fields without exposing message contents.

        Result rows return one actionable earliest campaign membership for each
        global contact, and never combine independently sorted membership IDs
        and campaign IDs into a mismatched pair.
        """
        self._page(limit, offset)
        term = clean_text(query).strip()
        if len(term) < 2 or len(term) > 100:
            raise ValueError("Enter 2 to 100 characters to search")
        if kind not in {"contacts", "leads"}:
            raise ValueError("Search contacts or leads")
        pattern = self.store._like(term)
        if kind == "contacts":
            clause = """(lower(c.full_name) LIKE lower(?) ESCAPE '\\'
                         OR lower(c.email) LIKE lower(?) ESCAPE '\\'
                         OR lower(c.company) LIKE lower(?) ESCAPE '\\')"""
            params: list[Any] = [pattern, pattern, pattern]
            count = self.store.connection.execute(
                f"SELECT COUNT(*) AS count FROM contacts c WHERE {clause}", params,
            ).fetchone()
            rows = self.store._rows(
                f"""SELECT c.id, c.full_name, c.email, c.company, c.title,
                           c.category,
                           (SELECT COUNT(*) FROM campaign_contacts cc
                            WHERE cc.contact_id = c.id) AS campaign_count,
                           (SELECT cc.id FROM campaign_contacts cc
                            WHERE cc.contact_id = c.id
                            ORDER BY cc.created_at ASC, cc.id ASC LIMIT 1)
                            AS campaign_contact_id,
                           (SELECT cc.campaign_id FROM campaign_contacts cc
                            WHERE cc.contact_id = c.id
                            ORDER BY cc.created_at ASC, cc.id ASC LIMIT 1)
                            AS campaign_id
                    FROM contacts c WHERE {clause}
                    ORDER BY lower(c.full_name), c.id
                    LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            )
        else:
            clause = """l.workspace_id = ? AND
                        (lower(l.lead_name) LIKE lower(?) ESCAPE '\\'
                         OR lower(l.email) LIKE lower(?) ESCAPE '\\'
                         OR lower(l.company) LIKE lower(?) ESCAPE '\\')"""
            params = [self.sales.workspace_id, pattern, pattern, pattern]
            count = self.store.connection.execute(
                f"SELECT COUNT(*) AS count FROM sales_leads l WHERE {clause}", params,
            ).fetchone()
            rows = self.store._rows(
                f"""SELECT l.id, l.lead_name, l.email, l.company,
                           l.lead_status, l.total_deal_value, l.cash_collected,
                           l.updated_at
                    FROM sales_leads l WHERE {clause}
                    ORDER BY lower(l.lead_name), l.id LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            )
        return {
            "items": rows, "total": int(count["count"] or 0),
            "limit": limit, "offset": offset, "kind": kind, "query": term,
        }

    def accounts(
        self, *, search: str = "", limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """Company grouping is inferred from normalized nonempty name only.

        It is not an externally verified corporate identity or subsidiary
        hierarchy. Global contacts plus same-workspace Sales Tracker leads are
        discoverable; each aggregate is computed independently (no fanout).
        """
        self._page(limit, offset)
        term = clean_text(search).strip()
        if len(term) > 100:
            raise ValueError("Company search must not exceed 100 characters")
        where = "WHERE lower(company_key) LIKE lower(?) ESCAPE '\\'" if term else ""
        params: list[Any] = [self.store._like(term)] if term else []
        common = """WITH companies AS (
            SELECT lower(trim(company)) AS company_key, MIN(trim(company)) AS display_name
            FROM contacts WHERE trim(company) <> '' GROUP BY lower(trim(company))
            UNION ALL
            SELECT lower(trim(company)), MIN(trim(company))
            FROM sales_leads WHERE trim(company) <> '' AND workspace_id = ?
            GROUP BY lower(trim(company))
        ), names AS (
            SELECT company_key, MIN(display_name) AS company_name
            FROM companies GROUP BY company_key
        )"""
        values = [self.sales.workspace_id, *params]
        total = self.store.connection.execute(
            common + f" SELECT COUNT(*) AS count FROM names {where}", values,
        ).fetchone()
        rows = self.store._rows(
            common + f""" SELECT n.company_key, n.company_name,
                 (SELECT COUNT(*) FROM contacts c
                  WHERE lower(trim(c.company)) = n.company_key) AS contacts,
                 (SELECT COUNT(DISTINCT cc.campaign_id) FROM contacts c
                  JOIN campaign_contacts cc ON cc.contact_id = c.id
                  WHERE lower(trim(c.company)) = n.company_key) AS campaigns,
                 (SELECT COUNT(*) FROM sales_leads l
                  WHERE lower(trim(l.company)) = n.company_key
                  AND l.workspace_id = ?) AS sales_leads,
                 (SELECT COUNT(*) FROM sales_leads l
                  WHERE lower(trim(l.company)) = n.company_key
                  AND l.workspace_id = ? AND l.lead_status = 'won') AS won_leads
              FROM names n {where}
              ORDER BY n.company_name, n.company_key LIMIT ? OFFSET ?""",
            [self.sales.workspace_id, self.sales.workspace_id,
             self.sales.workspace_id, *params, limit, offset],
        )
        return {"items": rows, "total": int(total["count"] or 0),
                "limit": limit, "offset": offset, "search": term,
                "identity_rule": "Grouped by case-insensitive trimmed company name"}

    def account(self, company: str, *, limit: int = 25, offset: int = 0) -> dict[str, Any]:
        self._page(limit, offset)
        key = self._company_key(company)
        exists = self.store._row(
            """SELECT 1 AS found FROM contacts WHERE lower(trim(company)) = ?
               UNION ALL
               SELECT 1 FROM sales_leads WHERE lower(trim(company)) = ? AND workspace_id = ?
               LIMIT 1""",
            (key, key, self.sales.workspace_id),
        )
        if not exists:
            raise KeyError("Company not found")
        contact_total = self.store.connection.execute(
            "SELECT COUNT(*) AS count FROM contacts WHERE lower(trim(company)) = ?", (key,),
        ).fetchone()
        contacts = self.store._rows(
            """SELECT c.id, c.full_name, c.email, c.title, c.category,
                      (SELECT COUNT(*) FROM campaign_contacts cc
                       WHERE cc.contact_id = c.id) AS campaign_count,
                      (SELECT cc.id FROM campaign_contacts cc
                       WHERE cc.contact_id = c.id
                       ORDER BY cc.created_at, cc.id LIMIT 1) AS campaign_contact_id,
                      (SELECT cc.campaign_id FROM campaign_contacts cc
                       WHERE cc.contact_id = c.id
                       ORDER BY cc.created_at, cc.id LIMIT 1) AS campaign_id
               FROM contacts c WHERE lower(trim(c.company)) = ?
               ORDER BY lower(c.full_name), c.id LIMIT ? OFFSET ?""",
            (key, limit, offset),
        )
        lead_total = self.store.connection.execute(
            """SELECT COUNT(*) AS count FROM sales_leads
               WHERE lower(trim(company)) = ? AND workspace_id = ?""",
            (key, self.sales.workspace_id),
        ).fetchone()
        leads = self.store._rows(
            """SELECT id, lead_name, lead_status, email, total_deal_value,
                      cash_collected, last_touch_at
               FROM sales_leads WHERE lower(trim(company)) = ? AND workspace_id = ?
               ORDER BY lower(lead_name), id LIMIT ? OFFSET ?""",
            (key, self.sales.workspace_id, limit, offset),
        )
        coverage = self.store._row(
            """SELECT COUNT(DISTINCT cc.campaign_id) AS campaigns,
                      COUNT(DISTINCT CASE WHEN cc.status = 'replied'
                          THEN cc.id END) AS replied_memberships,
                      COUNT(DISTINCT CASE WHEN m.direction = 'outbound'
                          THEN m.id END) AS outbound_messages,
                      COUNT(DISTINCT CASE WHEN m.direction = 'inbound'
                          THEN m.id END) AS inbound_messages
               FROM contacts c JOIN campaign_contacts cc ON cc.contact_id = c.id
               LEFT JOIN messages m ON m.campaign_contact_id = cc.id
               WHERE lower(trim(c.company)) = ?""",
            (key,),
        ) or {}
        pending = self.store._row(
            """SELECT COUNT(*) AS count FROM campaign_followup_tasks t
               JOIN campaign_contacts cc ON cc.id = t.campaign_contact_id
               JOIN contacts c ON c.id = cc.contact_id
               WHERE lower(trim(c.company)) = ? AND t.status = 'open'
                 AND t.campaign_id = cc.campaign_id""",
            (key,),
        )
        return {
            "company_key": key, "company_name": key,
            "contacts": {"items": contacts, "total": int(contact_total["count"] or 0)},
            "sales_leads": {"items": leads, "total": int(lead_total["count"] or 0)},
            "coverage": {
                "campaigns": int(coverage.get("campaigns") or 0),
                "replied_memberships": int(coverage.get("replied_memberships") or 0),
                "outbound_messages": int(coverage.get("outbound_messages") or 0),
                "inbound_messages": int(coverage.get("inbound_messages") or 0),
                "open_contact_tasks": int(pending["count"] or 0),
            },
            "limit": limit, "offset": offset,
            "identity_rule": "Exact match on case-insensitive trimmed company name",
        }

    def revenue_attribution(
        self, *, limit: int = 25, offset: int = 0,
    ) -> dict[str, Any]:
        """First CRM link owns attribution of a lead's sales outcome.

        Attribution here is *association*, never causal proof that the campaign
        produced a sale. Each lead contributes cash/value to only one campaign,
        chosen by earliest link time and membership ID as deterministic tie.
        """
        self._page(limit, offset)
        ownership = """WITH allocated AS (
            SELECT cc.campaign_id, x.sales_lead_id,
                   l.lead_status, l.total_deal_value, l.cash_collected,
                   l.refund_clawback_amount,
                   ROW_NUMBER() OVER (
                       PARTITION BY x.sales_lead_id
                       ORDER BY x.linked_at ASC, x.campaign_contact_id ASC
                   ) AS position
            FROM campaign_sales_links x
            JOIN campaign_contacts cc ON cc.id = x.campaign_contact_id
            JOIN sales_leads l ON l.id = x.sales_lead_id
            WHERE l.workspace_id = ?
        ), allocated_first AS (
            SELECT * FROM allocated WHERE position = 1
        )"""
        rows = self.store._rows(
            ownership + """ SELECT ca.id AS campaign_id, ca.name AS campaign_name,
                ca.kind, ca.status,
                (SELECT COUNT(*) FROM campaign_contacts cc
                 WHERE cc.campaign_id = ca.id) AS contacts,
                (SELECT COUNT(*) FROM campaign_contacts cc
                 WHERE cc.campaign_id = ca.id AND cc.status = 'replied') AS replied,
                (SELECT COUNT(*) FROM campaign_contacts cc
                 JOIN campaign_reply_triage rt ON rt.campaign_contact_id = cc.id
                 WHERE cc.campaign_id = ca.id AND rt.review_status = 'triaged'
                   AND rt.outcome IN ('positive', 'meeting')) AS qualified_replies,
                (SELECT COUNT(*) FROM campaign_sales_links x
                 JOIN campaign_contacts cc ON cc.id = x.campaign_contact_id
                 WHERE cc.campaign_id = ca.id) AS converted_memberships,
                (SELECT COUNT(*) FROM allocated_first a
                 WHERE a.campaign_id = ca.id) AS attributed_leads,
                (SELECT COUNT(*) FROM allocated_first a
                 WHERE a.campaign_id = ca.id AND a.lead_status = 'won') AS won_deals,
                (SELECT COUNT(*) FROM allocated_first a
                 WHERE a.campaign_id = ca.id AND a.lead_status = 'lost') AS lost_deals,
                (SELECT COALESCE(SUM(a.total_deal_value),0) FROM allocated_first a
                 WHERE a.campaign_id = ca.id AND a.lead_status = 'won') AS booked_value,
                (SELECT COALESCE(SUM(a.cash_collected),0) FROM allocated_first a
                 WHERE a.campaign_id = ca.id AND a.lead_status = 'won') AS recorded_cash,
                (SELECT COALESCE(SUM(a.cash_collected - a.refund_clawback_amount),0)
                 FROM allocated_first a WHERE a.campaign_id = ca.id
                   AND a.lead_status = 'won') AS cash_less_clawbacks
                FROM campaigns ca ORDER BY lower(ca.name), ca.id
                LIMIT ? OFFSET ?""",
            (self.sales.workspace_id, limit, offset),
        )
        count = self.store.connection.execute(
            "SELECT COUNT(*) AS count FROM campaigns",
        ).fetchone()
        overall = self.store._row(
            ownership + """ SELECT COUNT(*) AS attributed_leads,
                   COALESCE(SUM(CASE WHEN lead_status = 'won' THEN 1 ELSE 0 END),0)
                      AS won_deals,
                   COALESCE(SUM(CASE WHEN lead_status = 'won'
                                THEN total_deal_value ELSE 0 END),0) AS booked_value,
                   COALESCE(SUM(CASE WHEN lead_status = 'won'
                                THEN cash_collected ELSE 0 END),0) AS recorded_cash,
                   COALESCE(SUM(CASE WHEN lead_status = 'won'
                                THEN cash_collected-refund_clawback_amount ELSE 0 END),0)
                      AS cash_less_clawbacks
               FROM allocated_first""",
            (self.sales.workspace_id,),
        ) or {}
        return {
            "items": rows, "total": int(count["count"] or 0), "limit": limit,
            "offset": offset,
            "overall": {
                "attributed_leads": int(overall.get("attributed_leads") or 0),
                "won_deals": int(overall.get("won_deals") or 0),
                "booked_value": round(float(overall.get("booked_value") or 0), 2),
                "recorded_cash": round(float(overall.get("recorded_cash") or 0), 2),
                "cash_less_clawbacks": round(
                    float(overall.get("cash_less_clawbacks") or 0), 2),
            },
            "attribution_rule": (
                "Each sales lead is associated with its earliest CRM campaign-sales "
                "link. This is not proof of marketing causality."
            ),
            "value_units": "Sales Tracker monetary units; do not sum across currencies",
        }
