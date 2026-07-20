from __future__ import annotations

import calendar
import json
import math
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, TYPE_CHECKING

from .models import clean_text, normalize_email, parse_datetime, to_utc_iso, utc_now

if TYPE_CHECKING:
    from .store import OutreachStore


WORKSPACE_ID = "local"

LEAD_STATUS_LABELS = {
    "new": "New",
    "proposal": "Proposal",
    "deposit": "Deposit",
    "follow_up_ongoing": "Follow-Up Ongoing",
    "meeting_follow_up": "Meeting Follow-Up",
    "won": "Won",
    "lost": "Lost",
}
MEETING_STATUS_LABELS = {
    "": "Not set",
    "show": "Show",
    "no_show": "No-Show",
    "rescheduled_by_us": "Rescheduled By Us",
    "rescheduled_by_them": "Rescheduled By Them",
    "cancel": "Cancel",
    "dq": "DQ",
}
SALE_TYPE_LABELS = {
    "": "Not set",
    "one_call": "1-Call Sale",
    "follow_up": "Follow-Up Sale",
}
LOSS_REASON_LABELS = {
    "": "Not set",
    "price": "Price",
    "timing": "Timing",
    "partner_spouse": "Partner/Spouse",
    "competitor": "Competitor",
    "ghosted": "Ghosted",
    "not_qualified": "Not Qualified",
}

LEAD_STATUSES = tuple(LEAD_STATUS_LABELS)
MEETING_STATUSES = tuple(MEETING_STATUS_LABELS)
SALE_TYPES = tuple(SALE_TYPE_LABELS)
LOSS_REASONS = tuple(LOSS_REASON_LABELS)

TEXT_FIELDS = {
    "lead_name",
    "company",
    "email",
    "phone",
    "source",
    "setter_name",
    "closer_name",
    "lead_status",
    "meeting_status",
    "sale_type",
    "loss_reason",
    "notes",
}
DATETIME_FIELDS = {
    "date_created",
    "first_contact_at",
    "date_meeting_booked",
    "meeting_at",
    "deposit_received_at",
    "date_paid_in_full",
    "last_touch_at",
}
NUMBER_FIELDS = {
    "deposit_amount",
    "total_deal_value",
    "cash_collected",
    "refund_clawback_amount",
    "commission_percent",
}
EDITABLE_FIELDS = TEXT_FIELDS | DATETIME_FIELDS | NUMBER_FIELDS | {
    "offer_made",
    "position",
}


class SalesConflictError(RuntimeError):
    """Raised when a stale card tries to overwrite a newer revision."""


def _option_items(mapping: dict[str, str], *, include_empty: bool = False) -> list[dict[str, str]]:
    return [
        {"value": value, "label": label}
        for value, label in mapping.items()
        if include_empty or value
    ]


def _iso(value: object) -> str | None:
    if value in (None, ""):
        return None
    parsed = parse_datetime(value if isinstance(value, (str, datetime)) else str(value))
    return to_utc_iso(parsed) if parsed else None


def _as_date(value: date | str | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    parsed = date.fromisoformat(str(value)[:10])
    return parsed.isoformat()


def _safe_rate(numerator: float, denominator: float) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def _average(values: Iterable[float]) -> float:
    materialized = list(values)
    return round(sum(materialized) / len(materialized), 2) if materialized else 0.0


def _days_between(start: object, end: object) -> float | None:
    first = parse_datetime(start if isinstance(start, (str, datetime)) else None)
    second = parse_datetime(end if isinstance(end, (str, datetime)) else None)
    if not first or not second:
        return None
    return round((second - first).total_seconds() / 86400, 2)


def _minutes_between(start: object, end: object) -> float | None:
    first = parse_datetime(start if isinstance(start, (str, datetime)) else None)
    second = parse_datetime(end if isinstance(end, (str, datetime)) else None)
    if not first or not second:
        return None
    return round((second - first).total_seconds() / 60, 2)


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month):
        raise ValueError("month must use YYYY-MM")
    year, month_number = (int(part) for part in month.split("-"))
    last_day = calendar.monthrange(year, month_number)[1]
    return (
        datetime(year, month_number, 1, tzinfo=timezone.utc),
        datetime.combine(date(year, month_number, last_day), time.max, tzinfo=timezone.utc),
    )


def _wilson_interval(successes: int, total: int, *, z: float = 1.2816) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 1.0
    proportion = successes / total
    denominator = 1 + (z * z / total)
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(
            (proportion * (1 - proportion) / total) + (z * z / (4 * total * total))
        )
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


class SalesTracker:
    """Sales-card source of truth plus deterministic visibility and projections."""

    def __init__(self, store: "OutreachStore", *, workspace_id: str = WORKSPACE_ID):
        self.store = store
        self.workspace_id = clean_text(workspace_id) or WORKSPACE_ID

    def metadata(self) -> dict[str, Any]:
        setters = self._distinct("setter_name")
        closers = self._distinct("closer_name")
        activity_setters = [
            str(row["setter_name"])
            for row in self.store.connection.execute(
                """
                SELECT DISTINCT setter_name FROM sales_setter_activity
                WHERE workspace_id = ? AND setter_name <> '' ORDER BY lower(setter_name)
                """,
                (self.workspace_id,),
            ).fetchall()
        ]
        setters = sorted(set(setters) | set(activity_setters), key=str.casefold)
        return {
            "statuses": _option_items(LEAD_STATUS_LABELS),
            "meeting_statuses": _option_items(MEETING_STATUS_LABELS, include_empty=True),
            "sale_types": _option_items(SALE_TYPE_LABELS, include_empty=True),
            "loss_reasons": _option_items(LOSS_REASON_LABELS),
            "setters": setters,
            "closers": closers,
            "reps": sorted(set(setters) | set(closers), key=str.casefold),
            "sources": self._distinct("source"),
            "currency_default": "INR",
        }

    def _distinct(self, field: str) -> list[str]:
        if field not in {"setter_name", "closer_name", "source"}:
            raise ValueError("Unsupported sales metadata field")
        return [
            str(row[field])
            for row in self.store.connection.execute(
                f"""
                SELECT DISTINCT {field} FROM sales_leads
                WHERE workspace_id = ? AND {field} <> '' ORDER BY lower({field})
                """,
                (self.workspace_id,),
            ).fetchall()
        ]

    def _clean_changes(self, values: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in values.items():
            if key not in EDITABLE_FIELDS:
                continue
            if value is None:
                if key in DATETIME_FIELDS:
                    cleaned[key] = None
                continue
            if key in TEXT_FIELDS:
                cleaned[key] = normalize_email(value) if key == "email" else clean_text(value)
            elif key in DATETIME_FIELDS:
                cleaned[key] = _iso(value)
            elif key in NUMBER_FIELDS:
                cleaned[key] = round(float(value), 2)
            elif key == "offer_made":
                cleaned[key] = int(bool(value))
            elif key == "position":
                cleaned[key] = int(value)
        return cleaned

    def _validate_lead(self, lead: dict[str, Any]) -> dict[str, Any]:
        if not clean_text(lead.get("lead_name")):
            raise ValueError("Lead name is required")
        status = str(lead.get("lead_status") or "new")
        meeting_status = str(lead.get("meeting_status") or "")
        sale_type = str(lead.get("sale_type") or "")
        loss_reason = str(lead.get("loss_reason") or "")
        if status not in LEAD_STATUSES:
            raise ValueError("Unknown lead status")
        if meeting_status not in MEETING_STATUSES:
            raise ValueError("Unknown meeting status")
        if sale_type not in SALE_TYPES:
            raise ValueError("Unknown sale type")
        if loss_reason not in LOSS_REASONS:
            raise ValueError("Unknown loss reason")
        if status == "lost" and not loss_reason:
            raise ValueError("Loss reason is required when a lead is Lost")
        if status != "lost":
            lead["loss_reason"] = ""
        if status == "won" and float(lead.get("total_deal_value") or 0) <= 0:
            raise ValueError("Total deal value must be greater than zero when a lead is Won")
        for field in NUMBER_FIELDS:
            number = float(lead.get(field) or 0)
            if number < 0:
                raise ValueError(f"{field.replace('_', ' ').title()} cannot be negative")
        commission = float(lead.get("commission_percent") or 0)
        if commission > 100:
            raise ValueError("Commission percent cannot exceed 100")

        created = parse_datetime(lead.get("date_created"))
        first_contact = parse_datetime(lead.get("first_contact_at"))
        booked = parse_datetime(lead.get("date_meeting_booked"))
        meeting = parse_datetime(lead.get("meeting_at"))
        deposit_at = parse_datetime(lead.get("deposit_received_at"))
        paid = parse_datetime(lead.get("date_paid_in_full"))
        if created and first_contact and first_contact < created:
            raise ValueError("First contact cannot be earlier than date created")
        if booked and meeting and meeting < booked:
            raise ValueError("Meeting cannot be earlier than the date it was booked")
        if deposit_at and paid and paid < deposit_at:
            raise ValueError("Paid-in-full date cannot be earlier than the deposit date")
        return lead

    def _next_position(self, status: str) -> int:
        row = self.store.connection.execute(
            """
            SELECT COALESCE(MAX(position), 0) AS position FROM sales_leads
            WHERE workspace_id = ? AND lead_status = ?
            """,
            (self.workspace_id, status),
        ).fetchone()
        return int(row["position"] or 0) + 1000 if row else 1000

    def create_lead(self, values: dict[str, Any]) -> dict[str, Any]:
        now = to_utc_iso()
        lead_id = str(uuid.uuid4())
        cleaned = self._clean_changes(values)
        status = str(cleaned.get("lead_status") or "new")
        lead: dict[str, Any] = {
            "lead_name": "",
            "company": "",
            "email": "",
            "phone": "",
            "source": "",
            "setter_name": "",
            "closer_name": "",
            "lead_status": status,
            "date_created": cleaned.get("date_created") or now,
            "first_contact_at": None,
            "date_meeting_booked": None,
            "meeting_at": None,
            "meeting_status": "",
            "offer_made": 0,
            "sale_type": "",
            "loss_reason": "",
            "deposit_amount": 0.0,
            "deposit_received_at": None,
            "total_deal_value": 0.0,
            "cash_collected": 0.0,
            "date_paid_in_full": None,
            "refund_clawback_amount": 0.0,
            "commission_percent": 0.0,
            "last_touch_at": None,
            "notes": "",
            "position": self._next_position(status),
        }
        lead.update(cleaned)
        if float(lead.get("deposit_amount") or 0) > 0 and not lead.get("deposit_received_at"):
            lead["deposit_received_at"] = now
        lead = self._validate_lead(lead)
        won_at = now if status == "won" else None
        lost_at = now if status == "lost" else None
        fields = [
            "lead_name", "company", "email", "phone", "source", "setter_name",
            "closer_name", "lead_status", "date_created", "first_contact_at",
            "date_meeting_booked", "meeting_at", "meeting_status", "offer_made",
            "sale_type", "loss_reason", "deposit_amount", "deposit_received_at",
            "total_deal_value", "cash_collected", "date_paid_in_full",
            "refund_clawback_amount", "commission_percent", "last_touch_at", "notes",
            "position",
        ]
        with self.store.transaction(immediate=True) as connection:
            connection.execute(
                f"""
                INSERT INTO sales_leads (
                    id, workspace_id, {', '.join(fields)}, revision,
                    status_changed_at, won_at, lost_at, created_at, updated_at
                ) VALUES ({', '.join('?' for _ in range(2 + len(fields) + 6))})
                """,
                (
                    lead_id,
                    self.workspace_id,
                    *[lead.get(field) for field in fields],
                    1,
                    now,
                    won_at,
                    lost_at,
                    now,
                    now,
                ),
            )
            self._record_event(
                connection,
                lead_id=lead_id,
                event_type="lead_created",
                current_status=status,
                payload={"source": lead.get("source", "")},
                created_at=now,
            )
        return self.get_lead(lead_id)

    def _raw_lead(self, lead_id: str) -> dict[str, Any]:
        row = self.store.connection.execute(
            "SELECT * FROM sales_leads WHERE workspace_id = ? AND id = ?",
            (self.workspace_id, clean_text(lead_id)),
        ).fetchone()
        if not row:
            raise KeyError(f"Sales lead not found: {lead_id}")
        return dict(row)

    def get_lead(self, lead_id: str) -> dict[str, Any]:
        return self._decorate(self._raw_lead(lead_id))

    def update_lead(
        self,
        lead_id: str,
        values: dict[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        current = self._raw_lead(lead_id)
        if expected_revision is not None and int(current["revision"]) != expected_revision:
            raise SalesConflictError(
                "This lead was updated elsewhere. Refresh the board before saving again."
            )
        cleaned = self._clean_changes(values)
        if not cleaned:
            return self._decorate(current)
        merged = dict(current)
        merged.update(cleaned)
        now = to_utc_iso()
        previous_status = str(current["lead_status"])
        current_status = str(merged.get("lead_status") or previous_status)
        if current_status != previous_status:
            merged["status_changed_at"] = now
            cleaned["status_changed_at"] = now
            if "position" not in cleaned:
                cleaned["position"] = self._next_position(current_status)
                merged["position"] = cleaned["position"]
            if current_status == "won":
                cleaned["won_at"] = now
                merged["won_at"] = now
                cleaned["lost_at"] = None
                merged["lost_at"] = None
            elif current_status == "lost":
                cleaned["lost_at"] = now
                merged["lost_at"] = now
                cleaned["won_at"] = None
                merged["won_at"] = None
            else:
                cleaned["won_at"] = None
                cleaned["lost_at"] = None
                merged["won_at"] = None
                merged["lost_at"] = None
        if (
            float(merged.get("deposit_amount") or 0) > 0
            and not merged.get("deposit_received_at")
        ):
            cleaned["deposit_received_at"] = now
            merged["deposit_received_at"] = now
        merged = self._validate_lead(merged)
        if merged.get("loss_reason") != current.get("loss_reason"):
            cleaned["loss_reason"] = merged.get("loss_reason") or ""

        comparable = {
            key: value
            for key, value in cleaned.items()
            if current.get(key) != value
        }
        if not comparable:
            return self._decorate(current)
        with self.store.transaction(immediate=True) as connection:
            assignments = ", ".join(f"{key} = ?" for key in comparable)
            cursor = connection.execute(
                f"""
                UPDATE sales_leads
                SET {assignments}, revision = revision + 1, updated_at = ?
                WHERE workspace_id = ? AND id = ? AND revision = ?
                """,
                (
                    *comparable.values(),
                    now,
                    self.workspace_id,
                    lead_id,
                    int(current["revision"]),
                ),
            )
            if cursor.rowcount != 1:
                raise SalesConflictError(
                    "This lead was updated elsewhere. Refresh the board before saving again."
                )
            event_type = "status_changed" if current_status != previous_status else "lead_updated"
            self._record_event(
                connection,
                lead_id=lead_id,
                event_type=event_type,
                previous_status=previous_status,
                current_status=current_status,
                payload={"fields": sorted(comparable)},
                created_at=now,
            )
        return self.get_lead(lead_id)

    def move_lead(
        self,
        lead_id: str,
        status: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if status not in LEAD_STATUSES:
            raise ValueError("Unknown lead status")
        return self.update_lead(
            lead_id,
            {"lead_status": status},
            expected_revision=expected_revision,
        )

    def _record_event(
        self,
        connection: Any,
        *,
        lead_id: str,
        event_type: str,
        current_status: str,
        previous_status: str = "",
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO sales_lead_events (
                id, workspace_id, lead_id, event_type, previous_status,
                current_status, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                self.workspace_id,
                lead_id,
                clean_text(event_type),
                clean_text(previous_status),
                clean_text(current_status),
                json.dumps(payload or {}, ensure_ascii=False, default=str),
                created_at or to_utc_iso(),
            ),
        )

    def lead_events(self, lead_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self._raw_lead(lead_id)
        rows = self.store.connection.execute(
            """
            SELECT * FROM sales_lead_events
            WHERE workspace_id = ? AND lead_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (self.workspace_id, lead_id, max(1, min(limit, 500))),
        ).fetchall()
        result = []
        for item in rows:
            row = dict(item)
            row["payload"] = json.loads(row.pop("payload_json") or "{}")
            result.append(row)
        return result

    def _filter_sql(
        self,
        *,
        status: str = "",
        rep_name: str = "",
        source: str = "",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        search: str = "",
    ) -> tuple[str, list[Any]]:
        conditions = ["workspace_id = ?"]
        params: list[Any] = [self.workspace_id]
        if status:
            if status not in LEAD_STATUSES:
                raise ValueError("Unknown lead status")
            conditions.append("lead_status = ?")
            params.append(status)
        if rep_name:
            conditions.append("(lower(setter_name) = lower(?) OR lower(closer_name) = lower(?))")
            params.extend([clean_text(rep_name), clean_text(rep_name)])
        if source:
            conditions.append("lower(source) = lower(?)")
            params.append(clean_text(source))
        if start_date:
            conditions.append("date(date_created) >= date(?)")
            params.append(_as_date(start_date))
        if end_date:
            conditions.append("date(date_created) <= date(?)")
            params.append(_as_date(end_date))
        if search:
            term = self.store._like(clean_text(search))
            conditions.append(
                "(lead_name LIKE ? ESCAPE '\\' OR company LIKE ? ESCAPE '\\' "
                "OR email LIKE ? ESCAPE '\\' OR phone LIKE ? ESCAPE '\\')"
            )
            params.extend([term, term, term, term])
        return " AND ".join(conditions), params

    def list_leads(
        self,
        *,
        status: str = "",
        rep_name: str = "",
        source: str = "",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        search: str = "",
        sort_by: str = "updated_at",
        sort_direction: str = "desc",
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clause, params = self._filter_sql(
            status=status,
            rep_name=rep_name,
            source=source,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        sort_fields = {
            "updated_at": "updated_at",
            "date_created": "date_created",
            "lead_name": "lower(lead_name)",
            "company": "lower(company)",
            "status": "lead_status",
            "meeting_at": "meeting_at",
            "last_touch_at": "last_touch_at",
            "total_deal_value": "total_deal_value",
            "cash_collected": "cash_collected",
            "earnings": "((total_deal_value - refund_clawback_amount) * commission_percent)",
        }
        expression = sort_fields.get(sort_by, "updated_at")
        direction = "ASC" if sort_direction.lower() == "asc" else "DESC"
        total_row = self.store.connection.execute(
            f"SELECT COUNT(*) AS count FROM sales_leads WHERE {clause}", params
        ).fetchone()
        rows = self.store.connection.execute(
            f"""
            SELECT * FROM sales_leads WHERE {clause}
            ORDER BY {expression} {direction}, id ASC LIMIT ? OFFSET ?
            """,
            (*params, max(1, min(limit, 5000)), max(0, offset)),
        ).fetchall()
        return [self._decorate(dict(row)) for row in rows], int(total_row["count"] or 0)

    def board(
        self,
        *,
        rep_name: str = "",
        source: str = "",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        search: str = "",
    ) -> dict[str, Any]:
        clause, params = self._filter_sql(
            rep_name=rep_name,
            source=source,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        rows = self.store.connection.execute(
            f"""
            SELECT * FROM sales_leads WHERE {clause}
            ORDER BY position ASC, updated_at DESC, id ASC
            """,
            params,
        ).fetchall()
        leads = [self._decorate(dict(row)) for row in rows]
        grouped = {status: [] for status in LEAD_STATUSES}
        for lead in leads:
            grouped[str(lead["lead_status"])].append(lead)
        columns = [
            {
                "status": status,
                "label": LEAD_STATUS_LABELS[status],
                "items": grouped[status],
                "count": len(grouped[status]),
                "pipeline_value": round(
                    sum(float(item["total_deal_value"]) for item in grouped[status]), 2
                ),
            }
            for status in LEAD_STATUSES
        ]
        return {
            "columns": columns,
            "total": len(leads),
            "leaks": self._leak_counts(leads),
        }

    def _decorate(self, row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        current = now or utc_now()
        row["offer_made"] = bool(row.get("offer_made"))
        deal_value = float(row.get("total_deal_value") or 0)
        refunds = float(row.get("refund_clawback_amount") or 0)
        commission = float(row.get("commission_percent") or 0)
        row["earnings"] = round((deal_value - refunds) * (commission / 100), 2)
        row["net_revenue"] = round(deal_value - refunds, 2)

        last_touch = (
            parse_datetime(row.get("last_touch_at"))
            or parse_datetime(row.get("first_contact_at"))
            or parse_datetime(row.get("date_created"))
        )
        follow_up_age = max(0, (current - last_touch).days) if last_touch else 0
        row["follow_up_age_days"] = follow_up_age
        row["follow_up_aging"] = (
            row.get("lead_status") == "follow_up_ongoing" and follow_up_age >= 7
        )

        booking_lag = _days_between(row.get("date_meeting_booked"), row.get("meeting_at"))
        row["booking_lag_days"] = booking_lag
        row["booking_lag_alert"] = booking_lag is not None and booking_lag > 4

        deposit_received = parse_datetime(row.get("deposit_received_at"))
        deposit_age = (
            max(0, (current - deposit_received).days)
            if deposit_received and not row.get("date_paid_in_full")
            else 0
        )
        row["deposit_age_days"] = deposit_age
        row["deposit_unpaid_alert"] = (
            float(row.get("deposit_amount") or 0) > 0
            and not row.get("date_paid_in_full")
            and deposit_age >= 14
        )
        flags = []
        if row["booking_lag_alert"]:
            flags.append("booking_lag")
        if row["follow_up_aging"]:
            flags.append("follow_up_aging")
        if row["deposit_unpaid_alert"]:
            flags.append("deposit_unpaid")
        row["leak_flags"] = flags
        row["lead_status_label"] = LEAD_STATUS_LABELS.get(str(row.get("lead_status")), "")
        row["meeting_status_label"] = MEETING_STATUS_LABELS.get(
            str(row.get("meeting_status") or ""), ""
        )
        row["sale_type_label"] = SALE_TYPE_LABELS.get(str(row.get("sale_type") or ""), "")
        row["loss_reason_label"] = LOSS_REASON_LABELS.get(
            str(row.get("loss_reason") or ""), ""
        )
        return row

    def _leak_counts(self, leads: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "follow_up_aging": sum(bool(lead.get("follow_up_aging")) for lead in leads),
            "booking_lag": sum(bool(lead.get("booking_lag_alert")) for lead in leads),
            "deposit_unpaid": sum(bool(lead.get("deposit_unpaid_alert")) for lead in leads),
            "total": sum(bool(lead.get("leak_flags")) for lead in leads),
        }

    def upsert_activity(self, values: dict[str, Any]) -> dict[str, Any]:
        activity_date = _as_date(values.get("activity_date"))
        setter_name = clean_text(values.get("setter_name"))
        if not activity_date:
            raise ValueError("Activity date is required")
        if not setter_name:
            raise ValueError("Setter name is required")
        counts = {
            "dials_dms_sent": int(values.get("dials_dms_sent") or 0),
            "conversations": int(values.get("conversations") or 0),
            "declines": int(values.get("declines") or 0),
        }
        if any(number < 0 for number in counts.values()):
            raise ValueError("Daily activity counts cannot be negative")
        now = to_utc_iso()
        with self.store.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO sales_setter_activity (
                    id, workspace_id, activity_date, setter_name, dials_dms_sent,
                    conversations, declines, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, activity_date, setter_name) DO UPDATE SET
                    dials_dms_sent = excluded.dials_dms_sent,
                    conversations = excluded.conversations,
                    declines = excluded.declines,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    str(uuid.uuid4()),
                    self.workspace_id,
                    activity_date,
                    setter_name,
                    counts["dials_dms_sent"],
                    counts["conversations"],
                    counts["declines"],
                    clean_text(values.get("notes")),
                    now,
                    now,
                ),
            )
        row = self.store.connection.execute(
            """
            SELECT * FROM sales_setter_activity
            WHERE workspace_id = ? AND activity_date = ? AND setter_name = ?
            """,
            (self.workspace_id, activity_date, setter_name),
        ).fetchone()
        return dict(row) if row else {}

    def list_activity(
        self,
        *,
        setter_name: str = "",
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = ["workspace_id = ?"]
        params: list[Any] = [self.workspace_id]
        if setter_name:
            conditions.append("lower(setter_name) = lower(?)")
            params.append(clean_text(setter_name))
        if start_date:
            conditions.append("date(activity_date) >= date(?)")
            params.append(_as_date(start_date))
        if end_date:
            conditions.append("date(activity_date) <= date(?)")
            params.append(_as_date(end_date))
        clause = " AND ".join(conditions)
        total = self.store.connection.execute(
            f"SELECT COUNT(*) AS count FROM sales_setter_activity WHERE {clause}", params
        ).fetchone()
        rows = self.store.connection.execute(
            f"""
            SELECT * FROM sales_setter_activity WHERE {clause}
            ORDER BY activity_date DESC, lower(setter_name) ASC LIMIT ? OFFSET ?
            """,
            (*params, max(1, min(limit, 1000)), max(0, offset)),
        ).fetchall()
        return [dict(row) for row in rows], int(total["count"] or 0)

    def set_goal(
        self,
        month: str,
        *,
        revenue_goal: float,
        cash_goal: float = 0,
        currency: str = "INR",
    ) -> dict[str, Any]:
        _month_bounds(month)
        if revenue_goal < 0 or cash_goal < 0:
            raise ValueError("Sales goals cannot be negative")
        currency = clean_text(currency).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Currency must be a three-letter ISO code")
        now = to_utc_iso()
        with self.store.transaction(immediate=True) as connection:
            connection.execute(
                """
                INSERT INTO sales_monthly_goals (
                    workspace_id, month, revenue_goal, cash_goal, currency, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, month) DO UPDATE SET
                    revenue_goal = excluded.revenue_goal,
                    cash_goal = excluded.cash_goal,
                    currency = excluded.currency,
                    updated_at = excluded.updated_at
                """,
                (
                    self.workspace_id,
                    month,
                    round(float(revenue_goal), 2),
                    round(float(cash_goal), 2),
                    currency,
                    now,
                ),
            )
        return self.get_goal(month)

    def get_goal(self, month: str) -> dict[str, Any]:
        _month_bounds(month)
        row = self.store.connection.execute(
            """
            SELECT * FROM sales_monthly_goals WHERE workspace_id = ? AND month = ?
            """,
            (self.workspace_id, month),
        ).fetchone()
        if row:
            return dict(row)
        return {
            "workspace_id": self.workspace_id,
            "month": month,
            "revenue_goal": 0.0,
            "cash_goal": 0.0,
            "currency": "INR",
            "updated_at": "",
        }

    def dashboard(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        rep_name: str = "",
        source: str = "",
        search: str = "",
        goal_month: str = "",
    ) -> dict[str, Any]:
        today = utc_now().date()
        start = _as_date(start_date) or today.replace(day=1).isoformat()
        end = _as_date(end_date) or today.isoformat()
        if start > end:
            raise ValueError("Start date cannot be after end date")
        month = goal_month or end[:7]
        leads, _ = self.list_leads(
            rep_name=rep_name,
            source=source,
            search=search,
            start_date=start,
            end_date=end,
            limit=5000,
            sort_by="date_created",
        )
        activity, _ = self.list_activity(
            setter_name=rep_name,
            start_date=start,
            end_date=end,
            limit=1000,
        )
        if rep_name:
            activity = [
                item for item in activity if item["setter_name"].casefold() == rep_name.casefold()
            ]

        activity_by_setter: dict[str, dict[str, int]] = defaultdict(
            lambda: {"dials_dms_sent": 0, "conversations": 0, "declines": 0}
        )
        for item in activity:
            bucket = activity_by_setter[str(item["setter_name"])]
            for key in bucket:
                bucket[key] += int(item.get(key) or 0)

        setter_names = sorted(
            {str(lead["setter_name"]) for lead in leads if lead.get("setter_name")}
            | set(activity_by_setter),
            key=str.casefold,
        )
        setter_metrics = [
            self._setter_metrics(
                name,
                [lead for lead in leads if lead.get("setter_name") == name],
                activity_by_setter.get(name, {}),
            )
            for name in setter_names
        ]
        setter_summary = self._setter_metrics(
            "All setters",
            leads,
            {
                key: sum(values.get(key, 0) for values in activity_by_setter.values())
                for key in ("dials_dms_sent", "conversations", "declines")
            },
        )

        closer_names = sorted(
            {str(lead["closer_name"]) for lead in leads if lead.get("closer_name")},
            key=str.casefold,
        )
        closer_metrics = [
            self._closer_metrics(
                name, [lead for lead in leads if lead.get("closer_name") == name]
            )
            for name in closer_names
        ]
        closer_summary = self._closer_metrics("All closers", leads)

        won = [lead for lead in leads if lead["lead_status"] == "won"]
        deposits = [lead for lead in leads if float(lead["deposit_amount"]) > 0]
        paid = [lead for lead in deposits if lead.get("date_paid_in_full")]
        collection_days = [
            value
            for value in (
                _days_between(lead.get("deposit_received_at"), lead.get("date_paid_in_full"))
                for lead in paid
            )
            if value is not None and value >= 0
        ]
        revenue = round(sum(float(lead["total_deal_value"]) for lead in won), 2)
        cash = round(sum(float(lead["cash_collected"]) for lead in leads), 2)
        refunds = round(sum(float(lead["refund_clawback_amount"]) for lead in leads), 2)
        goal = self.get_goal(month)
        commissions: dict[str, float] = defaultdict(float)
        for lead in won:
            commissions[str(lead.get("closer_name") or "Unassigned")] += float(lead["earnings"])

        loss_breakdown = []
        lost = [lead for lead in leads if lead["lead_status"] == "lost"]
        for reason, label in LOSS_REASON_LABELS.items():
            if not reason:
                continue
            count = sum(lead.get("loss_reason") == reason for lead in lost)
            loss_breakdown.append(
                {
                    "reason": reason,
                    "label": label,
                    "count": count,
                    "percent": _safe_rate(count, len(lost)),
                }
            )

        money = {
            "deposits": round(sum(float(lead["deposit_amount"]) for lead in deposits), 2),
            "deposit_count": len(deposits),
            "total_sales": len(won),
            "revenue_generated": revenue,
            "cash_collected": cash,
            "deposit_to_paid_in_full_rate": _safe_rate(len(paid), len(deposits)),
            "average_days_to_collect": _average(collection_days),
            "refunds_clawbacks": refunds,
            "net_revenue": round(revenue - refunds, 2),
            "revenue_goal": float(goal["revenue_goal"]),
            "cash_goal": float(goal["cash_goal"]),
            "currency": goal["currency"],
            "goal_month": month,
            "goal_completion_percent": _safe_rate(revenue, float(goal["revenue_goal"])),
            "cash_goal_completion_percent": _safe_rate(cash, float(goal["cash_goal"])),
            "commissions_total": round(sum(commissions.values()), 2),
            "commissions_by_rep": [
                {"rep_name": name, "earnings": round(value, 2)}
                for name, value in sorted(commissions.items(), key=lambda item: item[0].casefold())
            ],
        }
        return {
            "filters": {
                "start_date": start,
                "end_date": end,
                "rep_name": rep_name,
                "source": source,
                "search": search,
                "date_basis": "lead_created",
            },
            "lead_count": len(leads),
            "setter_summary": setter_summary,
            "setter_metrics": setter_metrics,
            "closer_summary": closer_summary,
            "closer_metrics": closer_metrics,
            "money": money,
            "loss_reasons": loss_breakdown,
            "leaks": self._leak_counts(leads),
        }

    def _setter_metrics(
        self,
        name: str,
        leads: list[dict[str, Any]],
        activity: dict[str, int],
    ) -> dict[str, Any]:
        scheduled = [lead for lead in leads if lead.get("meeting_at")]
        shown = [lead for lead in leads if lead.get("meeting_status") == "show"]
        no_shows = [lead for lead in leads if lead.get("meeting_status") == "no_show"]
        cancels = [lead for lead in leads if lead.get("meeting_status") == "cancel"]
        dqs = [lead for lead in leads if lead.get("meeting_status") == "dq"]
        dispositioned = len(shown) + len(no_shows) + len(cancels) + len(dqs)
        speed_values = [
            value
            for value in (
                _minutes_between(lead.get("date_created"), lead.get("first_contact_at"))
                for lead in leads
            )
            if value is not None and value >= 0
        ]
        lag_values = [
            value
            for value in (
                _days_between(lead.get("date_meeting_booked"), lead.get("meeting_at"))
                for lead in scheduled
            )
            if value is not None and value >= 0
        ]
        conversations = int(activity.get("conversations") or 0)
        return {
            "rep_name": name,
            "dials_dms_sent": int(activity.get("dials_dms_sent") or 0),
            "conversations": conversations,
            "conversations_to_booked_rate": _safe_rate(len(scheduled), conversations),
            "speed_to_lead_minutes": _average(speed_values),
            "booking_lag_days": _average(lag_values),
            "calls_scheduled": len(scheduled),
            "calls_taken": len(shown),
            "declines": int(activity.get("declines") or 0),
            "cancels": len(cancels),
            "no_shows": len(no_shows),
            "rescheduled": sum(
                lead.get("meeting_status") in {"rescheduled_by_us", "rescheduled_by_them"}
                for lead in leads
            ),
            "show_up_rate": _safe_rate(len(shown), dispositioned),
            "dq_rate": _safe_rate(len(dqs), len(scheduled)),
            "dq_count": len(dqs),
        }

    def _closer_metrics(self, name: str, leads: list[dict[str, Any]]) -> dict[str, Any]:
        shown = [lead for lead in leads if lead.get("meeting_status") == "show"]
        offers = [lead for lead in shown if lead.get("offer_made")]
        won = [lead for lead in leads if lead.get("lead_status") == "won"]
        revenue = sum(float(lead.get("total_deal_value") or 0) for lead in won)
        return {
            "rep_name": name,
            "calls_taken": len(shown),
            "offers_made": len(offers),
            "offer_rate": _safe_rate(len(offers), len(shown)),
            "sales": len(won),
            "close_rate": _safe_rate(len(won), len(shown)),
            "close_rate_on_offers": _safe_rate(len(won), len(offers)),
            "one_call_sales": sum(lead.get("sale_type") == "one_call" for lead in won),
            "follow_up_sales": sum(lead.get("sale_type") == "follow_up" for lead in won),
            "average_deal_size": round(revenue / len(won), 2) if won else 0.0,
            "revenue_per_call": round(revenue / len(shown), 2) if shown else 0.0,
            "revenue_generated": round(revenue, 2),
            "follow_up_aging": sum(bool(lead.get("follow_up_aging")) for lead in leads),
        }

    def projection(self, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        forecast_month = clean_text(values.get("forecast_month")) or now.strftime("%Y-%m")
        month_start, month_end = _month_bounds(forecast_month)
        history_end = _as_date(values.get("history_end")) or now.date().isoformat()
        history_start = _as_date(values.get("history_start")) or (
            now.date() - timedelta(days=90)
        ).isoformat()
        if history_start > history_end:
            raise ValueError("Projection history start cannot be after history end")
        rep_name = clean_text(values.get("rep_name"))
        source = clean_text(values.get("source"))
        history, _ = self.list_leads(
            rep_name=rep_name,
            source=source,
            start_date=history_start,
            end_date=history_end,
            limit=5000,
        )
        all_leads, _ = self.list_leads(
            rep_name=rep_name,
            source=source,
            limit=5000,
        )
        forecast_floor = max(now, month_start)
        scheduled_future = [
            lead
            for lead in all_leads
            if (meeting := parse_datetime(lead.get("meeting_at")))
            and forecast_floor <= meeting <= month_end
            and lead.get("meeting_status") in {"", "rescheduled_by_us", "rescheduled_by_them"}
            and lead.get("lead_status") not in {"won", "lost"}
        ]
        scheduled = (
            int(values["meetings_scheduled"])
            if values.get("meetings_scheduled") is not None
            else len(scheduled_future)
        )
        if scheduled < 0:
            raise ValueError("Meetings scheduled cannot be negative")

        shown = [lead for lead in history if lead.get("meeting_status") == "show"]
        dispositioned = [
            lead
            for lead in history
            if lead.get("meeting_status") in {"show", "no_show", "cancel", "dq"}
        ]
        offers = [lead for lead in shown if lead.get("offer_made")]
        won = [lead for lead in history if lead.get("lead_status") == "won"]
        won_on_offer = [lead for lead in won if lead.get("offer_made")]
        pipeline_values = [
            float(lead.get("total_deal_value") or 0)
            for lead in history
            if float(lead.get("total_deal_value") or 0) > 0
        ]
        won_values = [float(lead["total_deal_value"]) for lead in won if lead["total_deal_value"]]
        defaults_used: list[str] = []

        def assumption(
            key: str,
            supplied: object,
            numerator: int,
            denominator: int,
            fallback: float,
        ) -> tuple[float, float, float, str]:
            if supplied is not None:
                expected = float(supplied) / 100
                if not 0 <= expected <= 1:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be between 0 and 100")
                return expected, max(0.0, expected - 0.1), min(1.0, expected + 0.1), "manual"
            if denominator:
                expected = numerator / denominator
                low, high = _wilson_interval(numerator, denominator)
                return expected, low, high, "historical"
            defaults_used.append(key)
            return fallback, max(0.0, fallback - 0.2), min(1.0, fallback + 0.2), "fallback"

        show_rate, show_low, show_high, show_source = assumption(
            "show_up_rate", values.get("show_up_rate"), len(shown), len(dispositioned), 0.70
        )
        offer_rate, offer_low, offer_high, offer_source = assumption(
            "offer_rate", values.get("offer_rate"), len(offers), len(shown), 0.60
        )
        close_rate, close_low, close_high, close_source = assumption(
            "close_rate", values.get("close_rate"), len(won_on_offer), len(offers), 0.25
        )
        if values.get("average_deal_size") is not None:
            average_deal = float(values["average_deal_size"])
            deal_source = "manual"
        elif won_values:
            average_deal = sum(won_values) / len(won_values)
            deal_source = "historical"
        elif pipeline_values:
            average_deal = sum(pipeline_values) / len(pipeline_values)
            deal_source = "pipeline"
        else:
            average_deal = 0.0
            deal_source = "missing"
            defaults_used.append("average_deal_size")
        if average_deal < 0:
            raise ValueError("Average deal size cannot be negative")
        historical_revenue = sum(won_values)
        historical_cash = sum(float(lead.get("cash_collected") or 0) for lead in won)
        if values.get("cash_collection_rate") is not None:
            cash_rate = float(values["cash_collection_rate"]) / 100
            cash_source = "manual"
        elif historical_revenue > 0:
            cash_rate = min(1.0, historical_cash / historical_revenue)
            cash_source = "historical"
        else:
            cash_rate = 0.65
            cash_source = "fallback"
            defaults_used.append("cash_collection_rate")
        if not 0 <= cash_rate <= 1:
            raise ValueError("Cash collection rate must be between 0 and 100")

        current_month_won = [
            lead
            for lead in all_leads
            if lead.get("lead_status") == "won"
            and (won_at := parse_datetime(lead.get("won_at")))
            and month_start <= won_at <= month_end
        ]
        current_revenue = round(
            sum(float(lead.get("total_deal_value") or 0) for lead in current_month_won), 2
        )
        current_cash = round(
            sum(float(lead.get("cash_collected") or 0) for lead in current_month_won), 2
        )

        def scenario(
            name: str,
            show: float,
            offer: float,
            close: float,
            deal: float,
            collection: float,
        ) -> dict[str, Any]:
            projected_shows = scheduled * show
            projected_offers = projected_shows * offer
            projected_sales = projected_offers * close
            incremental_revenue = projected_sales * deal
            incremental_cash = incremental_revenue * collection
            return {
                "name": name,
                "meetings": scheduled,
                "projected_shows": round(projected_shows, 1),
                "projected_offers": round(projected_offers, 1),
                "projected_sales": round(projected_sales, 1),
                "incremental_revenue": round(incremental_revenue, 2),
                "incremental_cash": round(incremental_cash, 2),
                "end_of_month_revenue": round(current_revenue + incremental_revenue, 2),
                "end_of_month_cash": round(current_cash + incremental_cash, 2),
            }

        scenarios = [
            scenario(
                "worst",
                show_low,
                offer_low,
                close_low,
                average_deal * 0.85,
                max(0.0, cash_rate - 0.10),
            ),
            scenario(
                "expected",
                show_rate,
                offer_rate,
                close_rate,
                average_deal,
                cash_rate,
            ),
            scenario(
                "best",
                show_high,
                offer_high,
                close_high,
                average_deal * 1.15,
                min(1.0, cash_rate + 0.10),
            ),
        ]
        goal = self.get_goal(forecast_month)
        return {
            "forecast_month": forecast_month,
            "history_start": history_start,
            "history_end": history_end,
            "rep_name": rep_name,
            "source": source,
            "current_revenue": current_revenue,
            "current_cash": current_cash,
            "currency": goal["currency"],
            "revenue_goal": float(goal["revenue_goal"]),
            "assumptions": {
                "meetings_scheduled": scheduled,
                "show_up_rate": round(show_rate * 100, 2),
                "offer_rate": round(offer_rate * 100, 2),
                "close_rate": round(close_rate * 100, 2),
                "average_deal_size": round(average_deal, 2),
                "cash_collection_rate": round(cash_rate * 100, 2),
            },
            "assumption_sources": {
                "show_up_rate": show_source,
                "offer_rate": offer_source,
                "close_rate": close_source,
                "average_deal_size": deal_source,
                "cash_collection_rate": cash_source,
            },
            "samples": {
                "meetings_dispositioned": len(dispositioned),
                "calls_taken": len(shown),
                "offers_made": len(offers),
                "sales": len(won),
            },
            "defaults_used": sorted(set(defaults_used)),
            "scenarios": scenarios,
        }
