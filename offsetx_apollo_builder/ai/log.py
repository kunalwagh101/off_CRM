"""Egress log.

Section 5.5.8: log every outbound call — provider, tier, task type, the exact
payload sent, timestamp — and give the owner a screen to inspect it.  The point
is that the guarantee is *verified* rather than trusted.

Payload retention is on by default here, unlike the older provider-call audit
which defaulted to off.  A log that records only "42 characters were sent"
cannot answer the question the owner actually has, which is "what did you send
about this person?".  Retention is bounded by row count and age so the file does
not grow without limit.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ..db import Database, open_database
from ..outreach.models import to_utc_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_egress_log (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    created_at TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    provider_name TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    jurisdiction TEXT NOT NULL DEFAULT '',
    tier TEXT NOT NULL DEFAULT '',
    policy TEXT NOT NULL DEFAULT '',
    data_class TEXT NOT NULL DEFAULT '',
    task_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    findings TEXT NOT NULL DEFAULT '[]',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    payload TEXT NOT NULL DEFAULT '{}',
    payload_summary TEXT NOT NULL DEFAULT '{}',
    response_text TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_ai_egress_created ON ai_egress_log(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ai_egress_workspace ON ai_egress_log(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ai_egress_provider ON ai_egress_log(provider_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_ai_egress_status ON ai_egress_log(status, created_at DESC);
"""

#: Keep the log useful without letting it grow forever.
MAX_ROWS = 20000
MAX_RESPONSE_CHARS = 20000
MAX_PAYLOAD_CHARS = 60000


class EgressLog:
    """The egress log, on SQLite or Postgres.

    Owns its own table and its own connection so the AI module can be lifted out
    of off_CRM without dragging the CRM schema with it. That independence is
    also why this is the first store to gain a Postgres option: it has no
    foreign keys into the CRM, so it can move on its own.

    **Why this one first.** On a deployment whose disk does not survive a
    restart, the egress log is the thing that must not be on that disk. It is
    the record of exactly what data left to which provider, and the security
    argument of the whole system is that the guarantee is *verified* rather than
    trusted. A verification trail that resets on every restart verifies nothing.

    Pass a path for SQLite, or a ``postgresql://`` URL for Postgres. Leaving
    both unset falls back to ``OFFSETX_DATABASE_URL``.
    """

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.target = database_path
        # Kept for callers that still read ``.path``; meaningless on Postgres
        # and deliberately not faked into something that looks like a file.
        self.path = Path(database_path) if database_path is not None else None
        self._lock = threading.RLock()
        self._connection: Database | None = None

    @property
    def backend(self) -> str:
        """``"sqlite"`` or ``"postgres"``. Worth showing in the inspector."""
        return self.connection.name

    @property
    def connection(self) -> Database:
        with self._lock:
            if self._connection is None:
                database = open_database(self.target)
                database.executescript(SCHEMA)
                self._connection = database
            return self._connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def record(
        self,
        *,
        workspace_id: str = "local",
        provider_id: str,
        provider_name: str = "",
        model_id: str = "",
        jurisdiction: str = "",
        tier: str = "",
        policy: str = "",
        data_class: str = "",
        task_type: str = "",
        status: str = "",
        error: str = "",
        findings: list[dict[str, Any]] | None = None,
        duration_ms: int = 0,
        payload: dict[str, Any] | None = None,
        payload_summary: dict[str, Any] | None = None,
        response_text: str = "",
    ) -> str:
        row_id = str(uuid.uuid4())
        payload_json = json.dumps(payload or {}, ensure_ascii=False, default=str)
        if len(payload_json) > MAX_PAYLOAD_CHARS:
            payload_json = payload_json[:MAX_PAYLOAD_CHARS] + '…"__truncated__":true}'
        with self._lock:
            self.connection.execute(
                "INSERT INTO ai_egress_log("
                " id, workspace_id, created_at, provider_id, provider_name, model_id,"
                " jurisdiction, tier, policy, data_class, task_type, status, error,"
                " findings, duration_ms, payload, payload_summary, response_text"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row_id,
                    workspace_id,
                    to_utc_iso(),
                    provider_id,
                    provider_name,
                    model_id,
                    jurisdiction,
                    tier,
                    policy,
                    data_class,
                    task_type,
                    status,
                    error[:2000],
                    json.dumps(findings or [], ensure_ascii=False),
                    int(duration_ms),
                    payload_json,
                    json.dumps(payload_summary or {}, ensure_ascii=False, default=str),
                    str(response_text)[:MAX_RESPONSE_CHARS],
                ),
            )
            self._trim()
        return row_id

    def _trim(self) -> None:
        row = self.connection.execute("SELECT COUNT(*) AS total FROM ai_egress_log").fetchone()
        if row and int(row["total"]) > MAX_ROWS:
            self.connection.execute(
                "DELETE FROM ai_egress_log WHERE id IN ("
                " SELECT id FROM ai_egress_log ORDER BY created_at ASC LIMIT ?"
                ")",
                (int(row["total"]) - MAX_ROWS,),
            )

    def list(
        self,
        *,
        workspace_id: str = "",
        provider_id: str = "",
        status: str = "",
        data_class: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("workspace_id", workspace_id),
            ("provider_id", provider_id),
            ("status", status),
            ("data_class", data_class),
        ):
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            total_row = self.connection.execute(
                f"SELECT COUNT(*) AS total FROM ai_egress_log{where}", params
            ).fetchone()
            rows = self.connection.execute(
                "SELECT id, workspace_id, created_at, provider_id, provider_name, model_id,"
                " jurisdiction, tier, policy, data_class, task_type, status, error,"
                " duration_ms, payload_summary"
                f" FROM ai_egress_log{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                [*params, max(1, min(limit, 200)), max(0, offset)],
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["payload_summary"] = _safe_json(item.get("payload_summary"), {})
            items.append(item)
        return items, int(total_row["total"]) if total_row else 0

    def get(self, log_id: str) -> dict[str, Any] | None:
        """Full record including the exact payload that was sent."""
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM ai_egress_log WHERE id = ?", (log_id,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = _safe_json(item.get("payload"), {})
        item["payload_summary"] = _safe_json(item.get("payload_summary"), {})
        item["findings"] = _safe_json(item.get("findings"), [])
        return item

    def stats(self, *, workspace_id: str = "") -> dict[str, Any]:
        clause = " WHERE workspace_id = ?" if workspace_id else ""
        params = [workspace_id] if workspace_id else []
        with self._lock:
            totals = self.connection.execute(
                "SELECT COUNT(*) AS calls,"
                " SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,"
                " SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed"
                f" FROM ai_egress_log{clause}",
                params,
            ).fetchone()
            by_tier = self.connection.execute(
                f"SELECT tier, COUNT(*) AS calls FROM ai_egress_log{clause}"
                " GROUP BY tier ORDER BY calls DESC",
                params,
            ).fetchall()
            # Every selected column is in the GROUP BY. SQLite tolerates bare
            # columns here and silently picks an arbitrary row for them;
            # Postgres refuses the query outright. Grouping on all three is
            # both portable and the answer that was actually meant.
            by_provider = self.connection.execute(
                f"SELECT provider_id, provider_name, jurisdiction, COUNT(*) AS calls"
                f" FROM ai_egress_log{clause}"
                " GROUP BY provider_id, provider_name, jurisdiction"
                " ORDER BY calls DESC LIMIT 20",
                params,
            ).fetchall()
        return {
            "calls": int(totals["calls"] or 0) if totals else 0,
            "blocked": int(totals["blocked"] or 0) if totals else 0,
            "failed": int(totals["failed"] or 0) if totals else 0,
            "by_tier": [dict(row) for row in by_tier],
            "by_provider": [dict(row) for row in by_provider],
        }

    def clear(self, *, workspace_id: str = "") -> int:
        with self._lock:
            if workspace_id:
                cursor = self.connection.execute(
                    "DELETE FROM ai_egress_log WHERE workspace_id = ?", (workspace_id,)
                )
            else:
                cursor = self.connection.execute("DELETE FROM ai_egress_log")
            return int(cursor.rowcount or 0)


def _safe_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return fallback
