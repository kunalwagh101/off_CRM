"""Durable crawl frontier for public-web discovery.

The frontier owns scheduling state only. URL safety remains in discovery.py and
is injected as `validator`, so there is still one public-web policy rather than
a second, inevitably-drifting copy.
"""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import urlsplit

BASE_REVISIT_SECONDS = 24 * 60 * 60
MAX_REVISIT_SECONDS = 30 * BASE_REVISIT_SECONDS
FAILURE_BACKOFF_SECONDS = 15 * 60
MAX_FAILURE_BACKOFF_SECONDS = BASE_REVISIT_SECONDS
DEFAULT_LEASE_SECONDS = 2 * 60


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def revisit_delay_seconds(
    *,
    changed: bool,
    unchanged_streak: int,
    stable_for_seconds: float,
) -> int:
    """Schedule changed pages quickly and back off pages that stay unchanged."""
    if changed:
        return BASE_REVISIT_SECONDS
    streak_delay = BASE_REVISIT_SECONDS * (2 ** min(max(1, unchanged_streak), 5))
    age_delay = max(BASE_REVISIT_SECONDS, int(max(0.0, stable_for_seconds) / 2))
    return min(MAX_REVISIT_SECONDS, max(streak_delay, age_delay))


@dataclass(frozen=True, slots=True)
class FrontierEntry:
    url: str
    host: str
    depth: int
    content_sha256: str
    last_crawled_at: str
    last_changed_at: str
    next_due_at: str
    lease_until: str
    unchanged_streak: int
    failure_count: int
    crawl_count: int
    change_count: int
    last_error: str
    discovered_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "FrontierEntry":
        return cls(**{name: row[name] for name in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        }


class CrawlFrontier:
    """SQLite-backed queue with adaptive revisits and expiring claim leases."""

    def __init__(
        self,
        path: Path | str,
        *,
        validator: Callable[[str], str],
    ) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.validator = validator
        self._lock = threading.RLock()
        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,
            timeout=5,
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS crawl_frontier (
                url TEXT PRIMARY KEY,
                host TEXT NOT NULL,
                depth INTEGER NOT NULL CHECK(depth >= 0),
                content_sha256 TEXT NOT NULL DEFAULT '',
                last_crawled_at TEXT NOT NULL DEFAULT '',
                last_changed_at TEXT NOT NULL DEFAULT '',
                next_due_at TEXT NOT NULL,
                lease_until TEXT NOT NULL DEFAULT '',
                unchanged_streak INTEGER NOT NULL DEFAULT 0 CHECK(unchanged_streak >= 0),
                failure_count INTEGER NOT NULL DEFAULT 0 CHECK(failure_count >= 0),
                crawl_count INTEGER NOT NULL DEFAULT 0 CHECK(crawl_count >= 0),
                change_count INTEGER NOT NULL DEFAULT 0 CHECK(change_count >= 0),
                last_error TEXT NOT NULL DEFAULT '',
                discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_crawl_frontier_due
            ON crawl_frontier(next_due_at, lease_until, depth)
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_crawl_frontier_host
            ON crawl_frontier(host, next_due_at)
            """
        )

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def __enter__(self) -> "CrawlFrontier":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def admit(self, value: str, depth: int, *, now: datetime | None = None) -> FrontierEntry:
        if depth < 0:
            raise ValueError("Frontier depth cannot be negative")
        url = self.validator(value)
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        if not host:
            raise ValueError("Frontier URL must have a hostname")
        timestamp = _iso(_utc(now))
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO crawl_frontier (
                    url, host, depth, next_due_at, discovered_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    host = excluded.host,
                    depth = MIN(crawl_frontier.depth, excluded.depth),
                    updated_at = excluded.updated_at
                """,
                (url, host, int(depth), timestamp, timestamp, timestamp),
            )
            row = self.connection.execute(
                "SELECT * FROM crawl_frontier WHERE url = ?", (url,)
            ).fetchone()
        assert row is not None
        return FrontierEntry.from_row(row)

    @staticmethod
    def _domain_clause(allowed_domains: Sequence[str]) -> tuple[str, list[str]]:
        domains = [item.lower().rstrip(".") for item in allowed_domains if item]
        if not domains:
            return "", []
        clauses: list[str] = []
        params: list[str] = []
        for domain in domains:
            clauses.append("(host = ? OR host LIKE ?)")
            params.extend([domain, f"%.{domain}"])
        return " AND (" + " OR ".join(clauses) + ")", params

    def claim_due(
        self,
        *,
        allowed_domains: Sequence[str],
        max_depth: int,
        limit: int,
        now: datetime | None = None,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> list[FrontierEntry]:
        if limit <= 0:
            return []
        current = _utc(now)
        current_iso = _iso(current)
        lease_until = _iso(current + timedelta(seconds=max(1, lease_seconds)))
        domain_sql, domain_params = self._domain_clause(allowed_domains)
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                rows = self.connection.execute(
                    f"""
                    SELECT * FROM crawl_frontier
                    WHERE next_due_at <= ?
                      AND (lease_until = '' OR lease_until <= ?)
                      AND depth <= ?
                      {domain_sql}
                    ORDER BY next_due_at ASC, discovered_at ASC, url ASC
                    LIMIT ?
                    """,
                    (current_iso, current_iso, int(max_depth), *domain_params, int(limit)),
                ).fetchall()
                claimed: list[FrontierEntry] = []
                for row in rows:
                    try:
                        self.validator(str(row["url"]))
                    except ValueError:
                        continue
                    self.connection.execute(
                        """
                        UPDATE crawl_frontier
                        SET lease_until = ?, updated_at = ?
                        WHERE url = ?
                        """,
                        (lease_until, current_iso, row["url"]),
                    )
                    payload = dict(row)
                    payload["lease_until"] = lease_until
                    payload["updated_at"] = current_iso
                    claimed.append(
                        FrontierEntry(
                            **{
                                name: payload[name]
                                for name in FrontierEntry.__dataclass_fields__
                            }
                        )
                    )
                self.connection.execute("COMMIT")
                return claimed
            except BaseException:
                self.connection.execute("ROLLBACK")
                raise

    def record_success(
        self,
        url: str,
        content_sha256: str,
        *,
        observed_at: datetime | None = None,
    ) -> FrontierEntry:
        if not content_sha256:
            raise ValueError("A successful crawl must record a content hash")
        now = _utc(observed_at)
        now_iso = _iso(now)
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT * FROM crawl_frontier WHERE url = ?", (url,)
                ).fetchone()
                if row is None:
                    raise KeyError("Frontier URL was not admitted")
                previous_hash = str(row["content_sha256"] or "")
                changed = not previous_hash or previous_hash != content_sha256
                previous_changed = _parse(str(row["last_changed_at"] or ""))
                if changed:
                    last_changed = now
                    streak = 0
                else:
                    last_changed = previous_changed or _parse(
                        str(row["last_crawled_at"] or "")
                    ) or now
                    streak = int(row["unchanged_streak"]) + 1
                stable_for = max(0.0, (now - last_changed).total_seconds())
                delay = revisit_delay_seconds(
                    changed=changed,
                    unchanged_streak=streak,
                    stable_for_seconds=stable_for,
                )
                self.connection.execute(
                    """
                    UPDATE crawl_frontier
                    SET content_sha256 = ?,
                        last_crawled_at = ?,
                        last_changed_at = ?,
                        next_due_at = ?,
                        lease_until = '',
                        unchanged_streak = ?,
                        failure_count = 0,
                        crawl_count = crawl_count + 1,
                        change_count = change_count + ?,
                        last_error = '',
                        updated_at = ?
                    WHERE url = ?
                    """,
                    (
                        content_sha256,
                        now_iso,
                        _iso(last_changed),
                        _iso(now + timedelta(seconds=delay)),
                        streak,
                        int(changed),
                        now_iso,
                        url,
                    ),
                )
                updated = self.connection.execute(
                    "SELECT * FROM crawl_frontier WHERE url = ?", (url,)
                ).fetchone()
                self.connection.execute("COMMIT")
            except BaseException:
                self.connection.execute("ROLLBACK")
                raise
        assert updated is not None
        return FrontierEntry.from_row(updated)

    def record_failure(
        self,
        url: str,
        error: object,
        *,
        observed_at: datetime | None = None,
    ) -> FrontierEntry:
        now = _utc(observed_at)
        now_iso = _iso(now)
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT * FROM crawl_frontier WHERE url = ?", (url,)
                ).fetchone()
                if row is None:
                    raise KeyError("Frontier URL was not admitted")
                failures = int(row["failure_count"]) + 1
                delay = min(
                    MAX_FAILURE_BACKOFF_SECONDS,
                    FAILURE_BACKOFF_SECONDS * (2 ** min(failures - 1, 6)),
                )
                self.connection.execute(
                    """
                    UPDATE crawl_frontier
                    SET next_due_at = ?,
                        lease_until = '',
                        failure_count = ?,
                        last_error = ?,
                        updated_at = ?
                    WHERE url = ?
                    """,
                    (
                        _iso(now + timedelta(seconds=delay)),
                        failures,
                        str(error).strip()[:500],
                        now_iso,
                        url,
                    ),
                )
                updated = self.connection.execute(
                    "SELECT * FROM crawl_frontier WHERE url = ?", (url,)
                ).fetchone()
                self.connection.execute("COMMIT")
            except BaseException:
                self.connection.execute("ROLLBACK")
                raise
        assert updated is not None
        return FrontierEntry.from_row(updated)

    def snapshot(
        self,
        *,
        allowed_domains: Sequence[str] = (),
        limit: int = 250,
    ) -> list[FrontierEntry]:
        domain_sql, params = self._domain_clause(allowed_domains)
        with self._lock:
            rows = self.connection.execute(
                f"""
                SELECT * FROM crawl_frontier
                WHERE 1 = 1 {domain_sql}
                ORDER BY next_due_at ASC, url ASC
                LIMIT ?
                """,
                (*params, max(1, min(1000, int(limit)))),
            ).fetchall()
        return [FrontierEntry.from_row(row) for row in rows]
