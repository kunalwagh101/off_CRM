from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from ..models import clean_text, normalize_email, parse_datetime, to_utc_iso, utc_now
from ..store import OutreachStore


class DeliverabilityStore:
    """Email-only persistence over the CRM's existing SQLite transaction boundary."""

    def __init__(self, outreach: OutreachStore):
        self.outreach = outreach
        self.connection = outreach.connection

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def _one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        return self._row(self.connection.execute(sql, tuple(params)).fetchone())

    def _many(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(sql, tuple(params)).fetchall()]

    @staticmethod
    def _decode_identity(row: dict[str, Any]) -> dict[str, Any]:
        row["provider_verified"] = bool(row.get("provider_verified"))
        row["check_details"] = json.loads(row.get("check_details_json") or "{}")
        return row

    @staticmethod
    def _decode_settings(row: dict[str, Any]) -> dict[str, Any]:
        for field in ("require_unsubscribe", "auto_pause_enabled"):
            row[field] = bool(row.get(field))
        return row

    @staticmethod
    def _decode_job(row: dict[str, Any]) -> dict[str, Any]:
        row["headers"] = json.loads(row.get("headers_json") or "{}")
        return row

    @staticmethod
    def _decode_suppression(row: dict[str, Any]) -> dict[str, Any]:
        row["active"] = bool(row.get("active"))
        return row

    # Sending identities -------------------------------------------------

    def upsert_identity(self, values: dict[str, Any]) -> dict[str, Any]:
        identity_id = clean_text(values.get("id")) or str(uuid.uuid4())
        now = to_utc_iso()
        existing = self._one(
            "SELECT created_at FROM email_sending_identities WHERE id = ?", (identity_id,)
        )
        created_at = str(existing["created_at"]) if existing else now
        payload = {
            "id": identity_id,
            "name": clean_text(values.get("name")),
            "provider_type": clean_text(values.get("provider_type")),
            "stream": clean_text(values.get("stream")),
            "from_email": normalize_email(values.get("from_email")),
            "reply_to": normalize_email(values.get("reply_to")),
            "domain": clean_text(values.get("domain")).lower(),
            "ses_identity": clean_text(values.get("ses_identity")).lower(),
            "aws_region": clean_text(values.get("aws_region")),
            "configuration_set": clean_text(values.get("configuration_set")),
            "dkim_selector": clean_text(values.get("dkim_selector")).lower(),
            "mail_from_domain": clean_text(values.get("mail_from_domain")).lower(),
            "sns_topic_arn": clean_text(values.get("sns_topic_arn")),
            "max_per_second": float(values.get("max_per_second", 1)),
            "max_batch_size": int(values.get("max_batch_size", 25)),
            "status": clean_text(values.get("status")) or "active",
        }
        with self.outreach.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO email_sending_identities (
                    id, name, provider_type, stream, from_email, reply_to, domain,
                    ses_identity, aws_region, configuration_set, dkim_selector,
                    mail_from_domain, sns_topic_arn, max_per_second, max_batch_size,
                    status, created_at, updated_at
                ) VALUES (
                    :id, :name, :provider_type, :stream, :from_email, :reply_to, :domain,
                    :ses_identity, :aws_region, :configuration_set, :dkim_selector,
                    :mail_from_domain, :sns_topic_arn, :max_per_second, :max_batch_size,
                    :status, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    provider_type = excluded.provider_type,
                    stream = excluded.stream,
                    from_email = excluded.from_email,
                    reply_to = excluded.reply_to,
                    domain = excluded.domain,
                    ses_identity = excluded.ses_identity,
                    aws_region = excluded.aws_region,
                    configuration_set = excluded.configuration_set,
                    dkim_selector = excluded.dkim_selector,
                    mail_from_domain = excluded.mail_from_domain,
                    sns_topic_arn = excluded.sns_topic_arn,
                    max_per_second = excluded.max_per_second,
                    max_batch_size = excluded.max_batch_size,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                {**payload, "created_at": created_at, "updated_at": now},
            )
        return self.get_identity(identity_id)

    def get_identity(self, identity_id: str) -> dict[str, Any]:
        row = self._one(
            "SELECT * FROM email_sending_identities WHERE id = ?", (identity_id,)
        )
        if not row:
            raise KeyError(f"Email sending identity not found: {identity_id}")
        return self._decode_identity(row)

    def list_identities(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        where = "" if include_archived else "WHERE status <> 'archived'"
        return [
            self._decode_identity(row)
            for row in self._many(
                f"SELECT * FROM email_sending_identities {where} ORDER BY created_at DESC"
            )
        ]

    def update_identity_check(
        self,
        identity_id: str,
        *,
        provider_verified: bool,
        spf_status: str,
        dkim_status: str,
        dmarc_status: str,
        alignment_status: str,
        dmarc_policy: str,
        details: dict[str, Any],
        checked_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = to_utc_iso(checked_at)
        with self.outreach.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE email_sending_identities SET
                    provider_verified = ?, spf_status = ?, dkim_status = ?,
                    dmarc_status = ?, alignment_status = ?, dmarc_policy = ?,
                    check_details_json = ?, last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(provider_verified),
                    spf_status,
                    dkim_status,
                    dmarc_status,
                    alignment_status,
                    clean_text(dmarc_policy),
                    json.dumps(details, ensure_ascii=False, default=str),
                    now,
                    now,
                    identity_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Email sending identity not found: {identity_id}")
        return self.get_identity(identity_id)

    # Per-campaign email settings ---------------------------------------

    def get_campaign_settings(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.outreach.get_campaign(campaign_id)
        if campaign["kind"] != "email":
            raise ValueError("Email delivery settings only apply to email campaigns")
        now = to_utc_iso()
        with self.outreach.transaction() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO email_campaign_settings (
                    campaign_id, daily_limit, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (campaign_id, int(campaign["daily_send_limit"]), now, now),
            )
            # The campaign's established daily limit remains the single hard
            # cap. Keeping the email view in sync prevents the durable path
            # from silently widening an older campaign's safety setting.
            conn.execute(
                """
                UPDATE email_campaign_settings SET daily_limit = ?, updated_at = ?
                WHERE campaign_id = ? AND daily_limit <> ?
                """,
                (
                    int(campaign["daily_send_limit"]),
                    now,
                    campaign_id,
                    int(campaign["daily_send_limit"]),
                ),
            )
        row = self._one(
            "SELECT * FROM email_campaign_settings WHERE campaign_id = ?", (campaign_id,)
        )
        assert row is not None
        return self._decode_settings(row)

    def update_campaign_settings(
        self, campaign_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        current = self.get_campaign_settings(campaign_id)
        allowed = {
            "stream",
            "provider_type",
            "identity_id",
            "daily_limit",
            "frequency_cap_days",
            "frequency_cap_max",
            "require_unsubscribe",
            "auto_pause_enabled",
            "health_sample_size",
            "max_hard_bounce_rate",
            "max_complaint_rate",
        }
        changes = {key: value for key, value in values.items() if key in allowed}
        if not changes:
            return current
        assignments = ", ".join(f"{key} = ?" for key in changes)
        params = [int(value) if isinstance(value, bool) else value for value in changes.values()]
        with self.outreach.transaction(immediate=True) as conn:
            conn.execute(
                f"UPDATE email_campaign_settings SET {assignments}, updated_at = ? WHERE campaign_id = ?",
                (*params, to_utc_iso(), campaign_id),
            )
            if "daily_limit" in changes:
                conn.execute(
                    "UPDATE campaigns SET daily_send_limit = ?, updated_at = ? WHERE id = ?",
                    (int(changes["daily_limit"]), to_utc_iso(), campaign_id),
                )
        return self.get_campaign_settings(campaign_id)

    # Permission and suppression ----------------------------------------

    def get_permission(self, email: str) -> dict[str, Any]:
        normalized = normalize_email(email)
        row = self._one(
            "SELECT * FROM email_contact_permissions WHERE email = ?", (normalized,)
        )
        if row:
            return row
        return {
            "email": normalized,
            "status": "unknown",
            "basis": "",
            "source": "",
            "evidence": "",
            "obtained_at": None,
            "expires_at": None,
        }

    def set_permission(
        self,
        email: str,
        *,
        status: str,
        basis: str = "",
        source: str = "",
        evidence: str = "",
        obtained_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO email_contact_permissions (
                    email, status, basis, source, evidence, obtained_at, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    status = excluded.status,
                    basis = excluded.basis,
                    source = excluded.source,
                    evidence = excluded.evidence,
                    obtained_at = excluded.obtained_at,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized,
                    status,
                    clean_text(basis),
                    clean_text(source),
                    clean_text(evidence),
                    to_utc_iso(obtained_at) if obtained_at else None,
                    to_utc_iso(expires_at) if expires_at else None,
                    now,
                    now,
                ),
            )
            if status == "denied":
                self._cancel_queued_for_email(conn, normalized, "permission_denied", now)
        return self.get_permission(normalized)

    def is_suppressed(self, email: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM email_suppressions WHERE email = ? AND active = 1",
            (normalize_email(email),),
        )
        return self._decode_suppression(row) if row else None

    def suppress(
        self,
        email: str,
        *,
        reason: str,
        source: str = "",
        provider_event_id: str = "",
    ) -> dict[str, Any]:
        normalized = normalize_email(email)
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            conn.execute(
                """
                INSERT INTO email_suppressions (
                    email, active, reason, source, provider_event_id, created_at, updated_at
                ) VALUES (?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    active = 1,
                    reason = excluded.reason,
                    source = excluded.source,
                    provider_event_id = excluded.provider_event_id,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized,
                    clean_text(reason),
                    clean_text(source),
                    clean_text(provider_event_id),
                    now,
                    now,
                ),
            )
            self._cancel_queued_for_email(conn, normalized, reason, now)
        row = self.is_suppressed(normalized)
        assert row is not None
        return row

    def unsuppress(self, email: str) -> dict[str, Any]:
        normalized = normalize_email(email)
        with self.outreach.transaction() as conn:
            cursor = conn.execute(
                "UPDATE email_suppressions SET active = 0, updated_at = ? WHERE email = ?",
                (to_utc_iso(), normalized),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Suppression not found: {normalized}")
        row = self._one("SELECT * FROM email_suppressions WHERE email = ?", (normalized,))
        assert row is not None
        return self._decode_suppression(row)

    def list_suppressions(
        self, *, active_only: bool = True, limit: int = 200, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        where = "WHERE active = 1" if active_only else ""
        total = self._one(f"SELECT COUNT(*) AS count FROM email_suppressions {where}")
        rows = self._many(
            f"SELECT * FROM email_suppressions {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._decode_suppression(row) for row in rows], int(
            total["count"] if total else 0
        )

    @staticmethod
    def _cancel_queued_for_email(
        conn: sqlite3.Connection, email: str, reason: str, now: str
    ) -> None:
        jobs = conn.execute(
            """
            SELECT draft_id FROM email_send_jobs
            WHERE to_email = ? AND status IN ('queued', 'retry_wait')
            """,
            (email,),
        ).fetchall()
        conn.execute(
            """
            UPDATE email_send_jobs SET status = 'blocked', last_error = ?,
                finished_at = ?, updated_at = ?
            WHERE to_email = ? AND status IN ('queued', 'retry_wait')
            """,
            (clean_text(reason)[:1000], now, now, email),
        )
        draft_ids = [str(row["draft_id"]) for row in jobs]
        if draft_ids:
            placeholders = ",".join("?" for _ in draft_ids)
            conn.execute(
                f"""
                UPDATE drafts SET approval_status = 'cancelled_policy', send_error = ?,
                    sending_started_at = NULL, updated_at = ?
                WHERE id IN ({placeholders}) AND sent_at IS NULL
                """,
                (clean_text(reason)[:1000], now, *draft_ids),
            )

    # Unsubscribe tokens -------------------------------------------------

    def create_unsubscribe_token(
        self, token_id: str, *, email: str, campaign_id: str, stream: str
    ) -> None:
        with self.outreach.transaction() as conn:
            conn.execute(
                """
                INSERT INTO email_unsubscribe_tokens (
                    token_id, email, campaign_id, stream, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (token_id, normalize_email(email), campaign_id, stream, to_utc_iso()),
            )

    def use_unsubscribe_token(self, token_id: str) -> dict[str, Any]:
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT * FROM email_unsubscribe_tokens WHERE token_id = ?", (token_id,)
            ).fetchone()
            if not row:
                raise KeyError("Unsubscribe link is invalid or expired")
            conn.execute(
                "UPDATE email_unsubscribe_tokens SET used_at = COALESCE(used_at, ?) WHERE token_id = ?",
                (now, token_id),
            )
        return dict(row)

    # Durable jobs -------------------------------------------------------

    def enqueue_job(self, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        now = to_utc_iso()
        job_id = clean_text(values.get("id")) or str(uuid.uuid4())
        key = clean_text(values.get("idempotency_key"))
        with self.outreach.transaction(immediate=True) as conn:
            existing = conn.execute(
                "SELECT * FROM email_send_jobs WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                return self._decode_job(dict(existing)), False
            draft = conn.execute(
                """
                SELECT d.id, d.revision, d.approval_status, d.sendable, d.sent_at,
                       cc.campaign_id
                FROM drafts d
                JOIN campaign_contacts cc ON cc.id = d.campaign_contact_id
                WHERE d.id = ? AND d.campaign_contact_id = ?
                """,
                (values["draft_id"], values["campaign_contact_id"]),
            ).fetchone()
            if not draft or str(draft["campaign_id"]) != str(values["campaign_id"]):
                raise KeyError("Draft is not part of this campaign contact")
            if int(draft["revision"]) != int(values["draft_revision"]):
                raise ValueError("Draft changed after preflight; run preflight again")
            if draft["sent_at"] or draft["approval_status"] != "approved" or not draft["sendable"]:
                raise ValueError("Only approved, sendable, unsent drafts can be queued")
            conn.execute(
                """
                INSERT INTO email_send_jobs (
                    id, campaign_id, campaign_contact_id, draft_id, draft_revision,
                    identity_id, stream, provider_type, lane_key, to_email, from_email,
                    subject, body, headers_json, idempotency_key, status, available_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    job_id,
                    values["campaign_id"],
                    values["campaign_contact_id"],
                    values["draft_id"],
                    int(values["draft_revision"]),
                    values.get("identity_id") or None,
                    values["stream"],
                    values["provider_type"],
                    values["lane_key"],
                    normalize_email(values["to_email"]),
                    normalize_email(values.get("from_email")),
                    str(values["subject"]),
                    str(values["body"]),
                    json.dumps(values.get("headers") or {}, ensure_ascii=False),
                    key,
                    values.get("available_at") or now,
                    now,
                    now,
                ),
            )
            cursor = conn.execute(
                """
                UPDATE drafts SET approval_status = 'queued', updated_at = ?
                WHERE id = ? AND revision = ? AND approval_status = 'approved'
                  AND sent_at IS NULL
                """,
                (now, values["draft_id"], int(values["draft_revision"])),
            )
            if cursor.rowcount != 1:
                raise ValueError("Draft could not be reserved for the delivery queue")
        return self.get_job(job_id), True

    def get_job(self, job_id: str) -> dict[str, Any]:
        row = self._one("SELECT * FROM email_send_jobs WHERE id = ?", (job_id,))
        if not row:
            raise KeyError(f"Email send job not found: {job_id}")
        return self._decode_job(row)

    def list_jobs(
        self,
        *,
        campaign_id: str = "",
        status: str = "",
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        params: list[Any] = []
        if campaign_id:
            where.append("j.campaign_id = ?")
            params.append(campaign_id)
        if status:
            where.append("j.status = ?")
            params.append(status)
        clause = " WHERE " + " AND ".join(where) if where else ""
        total = self._one(f"SELECT COUNT(*) AS count FROM email_send_jobs j{clause}", params)
        rows = self._many(
            f"""
            SELECT j.*, c.full_name, c.company
            FROM email_send_jobs j
            JOIN campaign_contacts cc ON cc.id = j.campaign_contact_id
            JOIN contacts c ON c.id = cc.contact_id
            {clause}
            ORDER BY j.created_at DESC LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        return [self._decode_job(row) for row in rows], int(total["count"] if total else 0)

    def claim_next(
        self,
        *,
        now: datetime,
        lease_seconds: int = 300,
        lane_counts: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        now_iso = to_utc_iso(now)
        lease_iso = to_utc_iso(now + timedelta(seconds=lease_seconds))
        with self.outreach.transaction(immediate=True) as conn:
            candidates = conn.execute(
                """
                SELECT j.*, c.daily_send_limit AS daily_limit, c.timezone,
                       COALESCE(i.max_per_second, 10) AS max_per_second,
                       COALESCE(i.max_batch_size, 100) AS max_batch_size,
                       i.status AS identity_status,
                       r.next_send_at, r.backoff_until
                FROM email_send_jobs j
                JOIN campaigns c ON c.id = j.campaign_id
                JOIN email_campaign_settings s ON s.campaign_id = j.campaign_id
                LEFT JOIN email_sending_identities i ON i.id = j.identity_id
                LEFT JOIN email_rate_state r ON r.lane_key = j.lane_key
                WHERE j.status IN ('queued', 'retry_wait')
                  AND j.available_at <= ?
                  AND c.status = 'active'
                  AND s.paused_reason = ''
                  AND (j.identity_id IS NULL OR i.status = 'active')
                ORDER BY j.available_at, j.created_at
                LIMIT 100
                """,
                (now_iso,),
            ).fetchall()
            selected: sqlite3.Row | None = None
            for row in candidates:
                if (lane_counts or {}).get(str(row["lane_key"]), 0) >= int(row["max_batch_size"]):
                    continue
                if row["next_send_at"] and str(row["next_send_at"]) > now_iso:
                    continue
                if row["backoff_until"] and str(row["backoff_until"]) > now_iso:
                    continue
                local = now.astimezone(ZoneInfo(str(row["timezone"])))
                local_start = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo)
                start_utc = local_start.astimezone(timezone.utc)
                end_utc = (local_start + timedelta(days=1)).astimezone(timezone.utc)
                sent_today = conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM messages m
                    JOIN campaign_contacts cc ON cc.id = m.campaign_contact_id
                    WHERE cc.campaign_id = ? AND m.direction = 'outbound'
                      AND m.sent_at >= ? AND m.sent_at < ?
                    """,
                    (row["campaign_id"], to_utc_iso(start_utc), to_utc_iso(end_utc)),
                ).fetchone()
                if int(sent_today["count"] if sent_today else 0) >= int(row["daily_limit"]):
                    resume_at = to_utc_iso(end_utc)
                    conn.execute(
                        """
                        UPDATE email_send_jobs SET available_at = ?, updated_at = ?
                        WHERE campaign_id = ? AND status IN ('queued', 'retry_wait')
                          AND available_at < ?
                        """,
                        (resume_at, now_iso, row["campaign_id"], resume_at),
                    )
                    continue
                selected = row
                break
            if selected is None:
                return None
            cursor = conn.execute(
                """
                UPDATE email_send_jobs SET status = 'sending', attempt_count = attempt_count + 1,
                    lease_expires_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('queued', 'retry_wait')
                """,
                (lease_iso, now_iso, selected["id"]),
            )
            if cursor.rowcount != 1:
                return None
            spacing = max(0.01, 1.0 / float(selected["max_per_second"]))
            next_send = to_utc_iso(now + timedelta(seconds=spacing))
            conn.execute(
                """
                INSERT INTO email_rate_state (lane_key, next_send_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(lane_key) DO UPDATE SET
                    next_send_at = excluded.next_send_at,
                    updated_at = excluded.updated_at
                """,
                (selected["lane_key"], next_send, now_iso),
            )
        return self.get_job(str(selected["id"]))

    def mark_retry(
        self, job_id: str, *, error: str, available_at: datetime, backoff_lane: bool = True
    ) -> None:
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT lane_key FROM email_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Email send job not found: {job_id}")
            conn.execute(
                """
                UPDATE email_send_jobs SET status = 'retry_wait', available_at = ?,
                    lease_expires_at = NULL, last_error = ?, updated_at = ? WHERE id = ?
                """,
                (to_utc_iso(available_at), clean_text(error)[:1000], now, job_id),
            )
            if backoff_lane:
                conn.execute(
                    """
                    INSERT INTO email_rate_state (
                        lane_key, backoff_until, consecutive_failures, updated_at
                    ) VALUES (?, ?, 1, ?)
                    ON CONFLICT(lane_key) DO UPDATE SET
                        backoff_until = excluded.backoff_until,
                        consecutive_failures = email_rate_state.consecutive_failures + 1,
                        updated_at = excluded.updated_at
                    """,
                    (row["lane_key"], to_utc_iso(available_at), now),
                )

    def defer_without_attempt(
        self, job_id: str, *, reason: str, available_at: datetime
    ) -> None:
        """Return a claimed job to the queue for a temporary policy condition."""
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            cursor = conn.execute(
                """
                UPDATE email_send_jobs SET status = 'retry_wait', available_at = ?,
                    attempt_count = MAX(0, attempt_count - 1), lease_expires_at = NULL,
                    last_error = ?, updated_at = ?
                WHERE id = ? AND status = 'sending'
                """,
                (
                    to_utc_iso(available_at),
                    clean_text(reason)[:1000],
                    now,
                    job_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Email job is no longer in a claimable sending state")

    def mark_terminal(self, job_id: str, *, status: str, error: str) -> None:
        if status not in {"blocked", "failed", "delivery_unknown", "cancelled"}:
            raise ValueError("Invalid terminal email job status")
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT draft_id FROM email_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Email send job not found: {job_id}")
            conn.execute(
                """
                UPDATE email_send_jobs SET status = ?, lease_expires_at = NULL,
                    last_error = ?, finished_at = ?, updated_at = ? WHERE id = ?
                """,
                (status, clean_text(error)[:1000], now, now, job_id),
            )
            draft_status = "cancelled_policy" if status in {"blocked", "cancelled"} else "send_failed_review"
            conn.execute(
                """
                UPDATE drafts SET approval_status = ?, send_error = ?,
                    sending_started_at = NULL, updated_at = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                (draft_status, clean_text(error)[:1000], now, row["draft_id"]),
            )

    def cancel_queued_job(self, job_id: str) -> dict[str, Any]:
        """Atomically cancel only a job that has not been claimed."""
        now = to_utc_iso()
        message = "Cancelled by operator"
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT draft_id FROM email_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Email send job not found: {job_id}")
            cursor = conn.execute(
                """
                UPDATE email_send_jobs SET status = 'cancelled', lease_expires_at = NULL,
                    last_error = ?, finished_at = ?, updated_at = ?
                WHERE id = ? AND status IN ('queued', 'retry_wait')
                """,
                (message, now, now, job_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only queued or waiting jobs can be cancelled")
            conn.execute(
                """
                UPDATE drafts SET approval_status = 'cancelled_policy', send_error = ?,
                    sending_started_at = NULL, updated_at = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                (message, now, row["draft_id"]),
            )
        return self.get_job(job_id)

    def cancel_for_reply(self, job_id: str) -> dict[str, Any]:
        """Cancel a claimed job when the CRM now shows a reply/stop."""
        now = to_utc_iso()
        message = "Recipient is no longer eligible after a reply or stop"
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT draft_id, status FROM email_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Email send job not found: {job_id}")
            if row["status"] != "cancelled":
                cursor = conn.execute(
                    """
                    UPDATE email_send_jobs SET status = 'cancelled', lease_expires_at = NULL,
                        last_error = ?, finished_at = ?, updated_at = ?
                    WHERE id = ? AND status IN ('queued', 'retry_wait', 'sending')
                    """,
                    (message, now, now, job_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError("Email job can no longer be cancelled for a reply")
            conn.execute(
                """
                UPDATE drafts SET approval_status = 'cancelled_reply', send_error = ?,
                    sending_started_at = NULL, updated_at = ?
                WHERE id = ? AND sent_at IS NULL
                """,
                (message, now, row["draft_id"]),
            )
        return self.get_job(job_id)

    def mark_accepted(self, job_id: str, *, provider_message_id: str) -> dict[str, Any]:
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT lane_key FROM email_send_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Email send job not found: {job_id}")
            conn.execute(
                """
                UPDATE email_send_jobs SET status = 'accepted', provider_message_id = ?,
                    accepted_at = COALESCE(accepted_at, ?), lease_expires_at = NULL,
                    last_error = '', updated_at = ? WHERE id = ?
                """,
                (clean_text(provider_message_id), now, now, job_id),
            )
            conn.execute(
                """
                UPDATE email_rate_state SET backoff_until = NULL,
                    consecutive_failures = 0, updated_at = ? WHERE lane_key = ?
                """,
                (now, row["lane_key"]),
            )
        return self.get_job(job_id)

    def recover_stale(self, *, now: datetime) -> dict[str, int]:
        now_iso = to_utc_iso(now)
        recovered = 0
        unknown = 0
        with self.outreach.transaction(immediate=True) as conn:
            rows = conn.execute(
                """
                SELECT j.id, j.draft_id, j.idempotency_key,
                       m.provider_message_id
                FROM email_send_jobs j
                LEFT JOIN messages m ON m.idempotency_key = j.idempotency_key
                WHERE j.status = 'sending' AND j.lease_expires_at < ?
                """,
                (now_iso,),
            ).fetchall()
            for row in rows:
                if row["provider_message_id"]:
                    conn.execute(
                        """
                        UPDATE email_send_jobs SET status = 'accepted', provider_message_id = ?,
                            accepted_at = COALESCE(accepted_at, ?), lease_expires_at = NULL,
                            last_error = '', updated_at = ? WHERE id = ?
                        """,
                        (row["provider_message_id"], now_iso, now_iso, row["id"]),
                    )
                    recovered += 1
                else:
                    message = "Worker stopped during provider delivery. Confirm provider state before retrying."
                    conn.execute(
                        """
                        UPDATE email_send_jobs SET status = 'delivery_unknown',
                            lease_expires_at = NULL, last_error = ?, finished_at = ?,
                            updated_at = ? WHERE id = ?
                        """,
                        (message, now_iso, now_iso, row["id"]),
                    )
                    conn.execute(
                        """
                        UPDATE drafts SET approval_status = 'send_failed_review', send_error = ?,
                            updated_at = ? WHERE id = ? AND sent_at IS NULL
                        """,
                        (message, now_iso, row["draft_id"]),
                    )
                    unknown += 1
        return {"recovered": recovered, "delivery_unknown": unknown}

    def recent_send_count(self, email: str, *, since: datetime) -> int:
        row = self._one(
            """
            SELECT COUNT(*) AS count FROM messages
            WHERE direction = 'outbound' AND lower(to_email) = ? AND sent_at >= ?
            """,
            (normalize_email(email), to_utc_iso(since)),
        )
        return int(row["count"] if row else 0)

    # Provider events and health ----------------------------------------

    def find_job_by_provider_message(self, provider_message_id: str) -> dict[str, Any] | None:
        row = self._one(
            "SELECT * FROM email_send_jobs WHERE provider_message_id = ?",
            (clean_text(provider_message_id),),
        )
        return self._decode_job(row) if row else None

    def record_delivery_event(self, values: dict[str, Any]) -> bool:
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO email_delivery_events (
                    id, provider_type, provider_event_id, job_id, campaign_id,
                    identity_id, provider_message_id, event_type, recipient_email,
                    diagnostic, raw_json, occurred_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    values["provider_type"],
                    values["provider_event_id"],
                    values.get("job_id") or None,
                    values.get("campaign_id") or None,
                    values.get("identity_id") or None,
                    clean_text(values.get("provider_message_id")),
                    values["event_type"],
                    normalize_email(values.get("recipient_email")),
                    clean_text(values.get("diagnostic"))[:2000],
                    json.dumps(values.get("raw") or {}, ensure_ascii=False, default=str),
                    values.get("occurred_at") or now,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                return False
            job_id = values.get("job_id")
            event_type = values["event_type"]
            if job_id and event_type == "delivered":
                conn.execute(
                    """
                    UPDATE email_send_jobs SET status = 'delivered', updated_at = ?
                    WHERE id = ? AND status IN ('accepted', 'deferred', 'delivered')
                    """,
                    (now, job_id),
                )
            elif job_id and event_type == "deferred":
                conn.execute(
                    """
                    UPDATE email_send_jobs SET status = 'deferred', updated_at = ?
                    WHERE id = ? AND status IN ('accepted', 'deferred')
                    """,
                    (now, job_id),
                )
            elif job_id and event_type in {
                "hard_bounce",
                "soft_bounce",
                "complaint",
                "rejected",
                "rendering_failed",
            }:
                conn.execute(
                    """
                    UPDATE email_send_jobs SET status = 'failed', last_error = ?,
                        finished_at = ?, updated_at = ? WHERE id = ?
                        AND status IN ('accepted', 'delivered', 'deferred', 'failed')
                    """,
                    (clean_text(values.get("diagnostic"))[:1000], now, now, job_id),
                )
        return True

    def health(self, campaign_id: str) -> dict[str, Any]:
        settings = self.get_campaign_settings(campaign_id)
        accepted = self._one(
            """
            SELECT COUNT(*) AS count FROM email_send_jobs
            WHERE campaign_id = ? AND accepted_at IS NOT NULL
            """,
            (campaign_id,),
        )
        events = self._many(
            """
            SELECT event_type, COUNT(DISTINCT COALESCE(job_id, provider_event_id)) AS count
            FROM email_delivery_events WHERE campaign_id = ?
            GROUP BY event_type
            """,
            (campaign_id,),
        )
        counts = {str(row["event_type"]): int(row["count"]) for row in events}
        sample = int(accepted["count"] if accepted else 0)
        bounce_rate = counts.get("hard_bounce", 0) / sample if sample else 0.0
        complaint_rate = counts.get("complaint", 0) / sample if sample else 0.0
        enough = sample >= int(settings["health_sample_size"])
        breached: list[str] = []
        if enough and bounce_rate > float(settings["max_hard_bounce_rate"]):
            breached.append("hard_bounce_rate")
        if enough and complaint_rate > float(settings["max_complaint_rate"]):
            breached.append("complaint_rate")
        return {
            "campaign_id": campaign_id,
            "accepted": sample,
            "delivered": counts.get("delivered", 0),
            "hard_bounces": counts.get("hard_bounce", 0),
            "complaints": counts.get("complaint", 0),
            "deferred": counts.get("deferred", 0),
            "hard_bounce_rate": round(bounce_rate, 6),
            "complaint_rate": round(complaint_rate, 6),
            "sample_required": int(settings["health_sample_size"]),
            "enough_data": enough,
            "breached": breached,
            "status": "paused" if settings["paused_reason"] else (
                "review" if breached else "healthy" if enough else "insufficient_data"
            ),
            "paused_reason": settings["paused_reason"],
        }

    def apply_health_pause(self, campaign_id: str) -> dict[str, Any]:
        report = self.health(campaign_id)
        settings = self.get_campaign_settings(campaign_id)
        if not settings["auto_pause_enabled"] or not report["breached"]:
            report["auto_paused_now"] = False
            return report
        campaign = self.outreach.get_campaign(campaign_id)
        if campaign["status"] != "active" and not settings["paused_reason"]:
            # A manual/archival pause belongs to the operator. Feedback may
            # report a breach, but deliverability must not take ownership of it.
            report["auto_paused_now"] = False
            return report
        reason = "Deliverability auto-pause: " + ", ".join(report["breached"])
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            paused = conn.execute(
                """
                UPDATE email_campaign_settings SET paused_reason = ?, paused_at = ?, updated_at = ?
                WHERE campaign_id = ? AND paused_reason = ''
                """,
                (reason, now, now, campaign_id),
            )
            if paused.rowcount:
                conn.execute(
                    "UPDATE campaigns SET status = 'paused', updated_at = ? WHERE id = ?",
                    (now, campaign_id),
                )
        updated = self.health(campaign_id)
        updated["auto_paused_now"] = bool(paused.rowcount)
        return updated

    def resume_health(self, campaign_id: str) -> dict[str, Any]:
        now = to_utc_iso()
        with self.outreach.transaction(immediate=True) as conn:
            row = conn.execute(
                "SELECT paused_reason FROM email_campaign_settings WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Email campaign settings not found: {campaign_id}")
            reason = str(row["paused_reason"] or "")
            conn.execute(
                """
                UPDATE email_campaign_settings SET paused_reason = '', paused_at = NULL,
                    updated_at = ? WHERE campaign_id = ?
                """,
                (now, campaign_id),
            )
            if reason.startswith("Deliverability auto-pause:"):
                conn.execute(
                    "UPDATE campaigns SET status = 'active', updated_at = ? WHERE id = ?",
                    (now, campaign_id),
                )
        return self.health(campaign_id)
