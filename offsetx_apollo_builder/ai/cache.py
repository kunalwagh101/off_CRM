"""Response cache: not sending the same thing twice.

**On the name.** The literature calls this a "semantic cache" and quotes hit
rates of 60-90%. Those figures come from chat and support systems where many
users ask the same handful of questions. off_CRM's core work is personalised
outreach, where every payload carries a different token and a different hook, so
the near-duplicate rate is close to zero and those numbers do not transfer.

Where it does pay, honestly:

* **re-running an eval suite** — the same cases against the same models, over and
  over, which is exactly what tuning looks like;
* **retries** after a transient provider failure;
* **repair rounds** that regenerate an identical payload;
* **public and code questions** asked more than once.

This is also not embedding-based. There is no embedding model here and adding
one would mean either a network call from a module whose whole point is to avoid
calls, or a heavy local dependency. What it does is **exact match plus lexical
near-match**, which covers the cases above completely and does not pretend to
understand meaning. Calling that "semantic" would be overclaiming.

---

**The safety property, and why the key is shaped as it is.**

The cache key includes the *constructed payload*, not the question. Payloads are
built per policy, so the same request produces different bytes at
``pseudonymous`` than at ``standard`` — verified, not assumed. Keying on the
payload therefore makes it **structurally impossible** for a response produced
from a richer payload to be served for a thinner one.

That matters more than it first appears. A response is not only shown to the
owner: it can travel back out as ``prior_drafts`` on a later call. A cache that
blurred policy boundaries would be a slow path for information derived from
tier A material to reach a tier C provider.

The key also includes the workspace, so one user's answers can never surface in
another's, and the provider, so "what did DeepSeek say" stays answerable.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..outreach.models import to_utc_iso
from .tiers import DataClass, DataPolicy

#: How long an entry stays usable. Model behaviour drifts, providers change what
#: sits behind a name, and a draft written six weeks ago against a template that
#: has since been rewritten is worse than no draft at all.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

#: Rows kept before the oldest are dropped. Small on purpose: this is a cache,
#: not an archive, and the egress log is where the permanent record lives.
DEFAULT_MAX_ROWS = 5000

#: Lexical overlap required for a near-match. Deliberately high — at this level
#: a "near" match is the same text with different whitespace, punctuation or
#: casing, not a different question that happens to share vocabulary. Serving a
#: stale answer to a genuinely different request is a worse failure than missing
#: a hit, so the threshold errs towards missing.
DEFAULT_SIMILARITY = 0.92

#: Classes that must never be cached, whatever else is configured. Mailbox
#: content cannot reach a payload at all, so this should be unreachable — it is
#: here so that if that ever changes, the cache is not the thing that quietly
#: starts persisting received mail.
NEVER_CACHE: frozenset[DataClass] = frozenset({DataClass.MAILBOX})

#: Task types whose answer may be reused. **An allowlist, so an unlisted task
#: type is never cached** — the same default-deny rule the provider registry and
#: the payload builder use.
#:
#: The line is: **cache work whose output is a fact, never work whose output is
#: a message.**
#:
#: This is not a preference. At ``pseudonymous`` policy a payload carries no
#: name — everyone is ``PERSON_1`` — so two different prospects with the same
#: title, category and an equivalent public hook produce a **byte-identical**
#: payload. Measured on real payloads: two logistics directors who both "opened
#: a new depot" score 1.000, an exact hit. Reusing that answer means both
#: prospects receive the *same email body*, which is the opposite of what this
#: system exists to do and precisely the pattern spam filters cluster on.
#:
#: A classification of a reply is a fact: same input, same answer, correct to
#: reuse. A drafted email is not.
CACHEABLE_TASK_TYPES: frozenset[str] = frozenset(
    {
        # Facts about an input. Reusing the answer is the point.
        "classify_reply",
        "summarise",
        "extract",
        "enrich",
        # A plan for a job. The same job should get the same plan.
        "orchestrator_plan",
        # A question and its answer. The classic cache case, and where the
        # published hit rates come from.
        "ai_chat",
    }
)

#: Named so the refusals are documented rather than merely absent. Nothing reads
#: this; it exists so the next person does not add one of these to the allowlist
#: without meeting the argument first.
NEVER_CACHE_TASK_TYPES: dict[str, str] = {
    "draft_email": (
        "The output is a message. Two prospects with the same title and an "
        "equivalent hook build the same payload, so a hit would send them the "
        "same email."
    ),
    "template_rewrite": (
        "Asking again is a request for something different. Returning the "
        "previous rewrite defeats the feature."
    ),
    "image_generation": (
        "The owner's refresh button regenerates against the same brief. A hit "
        "would hand back the identical picture and the button would look broken."
    ),
}


def is_cacheable(task_type: str, data_class: DataClass) -> bool:
    """Whether an answer to this kind of work may be stored and reused.

    Default-deny on both axes: an unlisted task type is not cached, and a
    never-cache data class is not cached whatever the task type says.
    """
    if data_class in NEVER_CACHE:
        return False
    return str(task_type or "").strip().lower() in CACHEABLE_TASK_TYPES

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_response_cache (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    cache_key TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    normalised TEXT NOT NULL DEFAULT '',
    shingles TEXT NOT NULL DEFAULT '[]',
    data_class TEXT NOT NULL,
    policy TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT '',
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_epoch REAL NOT NULL DEFAULT 0,
    hits INTEGER NOT NULL DEFAULT 0,
    last_hit_at TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cache_key
    ON ai_response_cache(cache_key);
CREATE INDEX IF NOT EXISTS ix_cache_partition
    ON ai_response_cache(partition_key, created_epoch DESC);

CREATE TABLE IF NOT EXISTS ai_cache_stats (
    workspace_id TEXT NOT NULL DEFAULT 'local',
    exact_hits INTEGER NOT NULL DEFAULT 0,
    near_hits INTEGER NOT NULL DEFAULT 0,
    misses INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (workspace_id)
);
"""

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(slots=True)
class CachedResponse:
    """A previously produced answer, and where it came from."""

    response: str
    provider_id: str
    model_id: str
    created_at: str
    kind: str = "exact"  # "exact" | "near"
    similarity: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "created_at": self.created_at,
            "kind": self.kind,
            "similarity": round(self.similarity, 4),
            "from_cache": True,
        }


def canonical_payload(payload: dict[str, Any]) -> str:
    """Stable JSON for hashing.

    Sorted keys and no incidental whitespace, so two payloads that differ only
    in dict ordering hash the same. Without this the exact-hit rate would depend
    on Python's dict iteration order, which is a silly reason to pay for a call.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def partition_key(
    *,
    workspace_id: str,
    data_class: DataClass,
    policy: DataPolicy,
    task_type: str,
    provider_id: str,
) -> str:
    """The bucket a near-match may search.

    Near-matching is confined to entries that share every one of these, so a
    fuzzy comparison can never reach across a policy or a workspace boundary
    however similar two texts look.
    """
    return "|".join(
        [
            str(workspace_id),
            data_class.value,
            policy.value,
            str(task_type),
            str(provider_id),
        ]
    )


def cache_key(*, partition: str, payload: dict[str, Any]) -> str:
    """Exact key: the partition plus the constructed payload bytes."""
    digest = hashlib.sha256()
    digest.update(partition.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(canonical_payload(payload).encode("utf-8"))
    return digest.hexdigest()


def _shingles(text: str, size: int = 3) -> list[str]:
    """Overlapping word triples.

    Word triples rather than single words because word-set overlap alone calls
    two different questions about the same subject "similar". Triples require
    the phrasing to line up, which is what the high threshold is protecting.
    """
    words = _WORD_RE.findall(text.lower())
    if len(words) < size:
        return [" ".join(words)] if words else []
    return [" ".join(words[i : i + size]) for i in range(len(words) - size + 1)]


def similarity(left: Iterable[str], right: Iterable[str]) -> float:
    """Jaccard overlap of two shingle sets."""
    a, b = set(left), set(right)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class ResponseCache:
    """Stores answers so identical work is not paid for twice.

    Holds no transport and no model. A cache that could call a provider would
    defeat its own purpose, and a structural test asserts it cannot.
    """

    def __init__(
        self,
        database_path: Path | str,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_rows: int = DEFAULT_MAX_ROWS,
        similarity_threshold: float = DEFAULT_SIMILARITY,
        near_match: bool = True,
    ) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(0, int(ttl_seconds))
        self.max_rows = max(1, int(max_rows))
        self.similarity_threshold = min(1.0, max(0.5, float(similarity_threshold)))
        self.near_match = bool(near_match)
        self._lock = threading.Lock()
        self._local = threading.local()
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    def connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ── reading ─────────────────────────────────────────────────────────────

    def get(
        self,
        *,
        payload: dict[str, Any],
        data_class: DataClass,
        policy: DataPolicy,
        task_type: str = "",
        provider_id: str = "",
        workspace_id: str = "local",
    ) -> CachedResponse | None:
        """An earlier answer to exactly this payload, or a near-identical one."""
        if not is_cacheable(task_type, data_class):
            return None
        partition = partition_key(
            workspace_id=workspace_id,
            data_class=data_class,
            policy=policy,
            task_type=task_type,
            provider_id=provider_id,
        )
        key = cache_key(partition=partition, payload=payload)
        now = time.time()

        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_response_cache WHERE cache_key = ?", (key,)
            ).fetchone()
            if row is not None and self._fresh(row, now):
                self._record_hit(conn, row["id"], workspace_id, "exact")
                return CachedResponse(
                    response=row["response"],
                    provider_id=row["provider_id"],
                    model_id=row["model_id"],
                    created_at=row["created_at"],
                    kind="exact",
                    similarity=1.0,
                )

            if not self.near_match:
                self._record_miss(conn, workspace_id)
                return None

            wanted = _shingles(canonical_payload(payload))
            if not wanted:
                self._record_miss(conn, workspace_id)
                return None

            best_row, best_score = None, 0.0
            candidates = conn.execute(
                "SELECT * FROM ai_response_cache WHERE partition_key = ? "
                "ORDER BY created_epoch DESC LIMIT 200",
                (partition,),
            ).fetchall()
            for candidate in candidates:
                if not self._fresh(candidate, now):
                    continue
                score = similarity(wanted, json.loads(candidate["shingles"]))
                if score > best_score:
                    best_row, best_score = candidate, score

            if best_row is not None and best_score >= self.similarity_threshold:
                self._record_hit(conn, best_row["id"], workspace_id, "near")
                return CachedResponse(
                    response=best_row["response"],
                    provider_id=best_row["provider_id"],
                    model_id=best_row["model_id"],
                    created_at=best_row["created_at"],
                    kind="near",
                    similarity=best_score,
                )

            self._record_miss(conn, workspace_id)
            return None

    def _fresh(self, row: sqlite3.Row, now: float) -> bool:
        if not self.ttl_seconds:
            return True
        return (now - float(row["created_epoch"])) <= self.ttl_seconds

    # ── writing ─────────────────────────────────────────────────────────────

    def put(
        self,
        *,
        payload: dict[str, Any],
        response: str,
        data_class: DataClass,
        policy: DataPolicy,
        task_type: str = "",
        provider_id: str = "",
        model_id: str = "",
        workspace_id: str = "local",
    ) -> bool:
        """Store an answer.  Returns whether it was stored.

        An empty response is not stored: caching "the provider returned nothing"
        would turn one transient failure into a week of them.
        """
        if not is_cacheable(task_type, data_class):
            return False
        if not str(response or "").strip():
            return False
        partition = partition_key(
            workspace_id=workspace_id,
            data_class=data_class,
            policy=policy,
            task_type=task_type,
            provider_id=provider_id,
        )
        key = cache_key(partition=partition, payload=payload)
        canonical = canonical_payload(payload)
        with self._lock, self.connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_response_cache
                    (id, workspace_id, cache_key, partition_key, normalised, shingles,
                     data_class, policy, task_type, provider_id, model_id, response,
                     created_at, created_epoch, hits, last_hit_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'')
                ON CONFLICT(cache_key) DO UPDATE SET
                    response=excluded.response,
                    provider_id=excluded.provider_id,
                    model_id=excluded.model_id,
                    created_at=excluded.created_at,
                    created_epoch=excluded.created_epoch
                """,
                (
                    uuid.uuid4().hex,
                    workspace_id,
                    key,
                    partition,
                    canonical[:4000],
                    json.dumps(_shingles(canonical)),
                    data_class.value,
                    policy.value,
                    task_type,
                    provider_id,
                    model_id,
                    response,
                    to_utc_iso(),
                    time.time(),
                ),
            )
            self._evict(conn)
        return True

    def _evict(self, conn: sqlite3.Connection) -> None:
        total = conn.execute("SELECT COUNT(*) AS n FROM ai_response_cache").fetchone()["n"]
        if total <= self.max_rows:
            return
        conn.execute(
            """
            DELETE FROM ai_response_cache WHERE id IN (
                SELECT id FROM ai_response_cache
                ORDER BY created_epoch ASC LIMIT ?
            )
            """,
            (total - self.max_rows,),
        )

    # ── housekeeping ────────────────────────────────────────────────────────

    def purge_expired(self) -> int:
        if not self.ttl_seconds:
            return 0
        cutoff = time.time() - self.ttl_seconds
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM ai_response_cache WHERE created_epoch < ?", (cutoff,)
            )
        return cursor.rowcount

    def clear(self, *, workspace_id: str = "") -> int:
        with self._lock, self.connection() as conn:
            if workspace_id:
                cursor = conn.execute(
                    "DELETE FROM ai_response_cache WHERE workspace_id = ?",
                    (workspace_id,),
                )
            else:
                cursor = conn.execute("DELETE FROM ai_response_cache")
        return cursor.rowcount

    # ── measurement ─────────────────────────────────────────────────────────

    def _record_hit(
        self, conn: sqlite3.Connection, row_id: str, workspace_id: str, kind: str
    ) -> None:
        conn.execute(
            "UPDATE ai_response_cache SET hits = hits + 1, last_hit_at = ? WHERE id = ?",
            (to_utc_iso(), row_id),
        )
        column = "exact_hits" if kind == "exact" else "near_hits"
        conn.execute(
            f"""
            INSERT INTO ai_cache_stats (workspace_id, {column}) VALUES (?, 1)
            ON CONFLICT(workspace_id) DO UPDATE SET {column} = {column} + 1
            """,
            (workspace_id,),
        )

    def _record_miss(self, conn: sqlite3.Connection, workspace_id: str) -> None:
        conn.execute(
            """
            INSERT INTO ai_cache_stats (workspace_id, misses) VALUES (?, 1)
            ON CONFLICT(workspace_id) DO UPDATE SET misses = misses + 1
            """,
            (workspace_id,),
        )

    def stats(self, *, workspace_id: str = "local") -> dict[str, Any]:
        """Hit rate, so the owner can tell whether this is earning its place.

        Reported rather than assumed, because the published 60-90% figures do
        not apply to personalised outreach and the only way to know what it is
        worth here is to measure it.
        """
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_cache_stats WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
            rows = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_response_cache WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
        exact = row["exact_hits"] if row else 0
        near = row["near_hits"] if row else 0
        misses = row["misses"] if row else 0
        looked_up = exact + near + misses
        return {
            "entries": rows,
            "exact_hits": exact,
            "near_hits": near,
            "misses": misses,
            "lookups": looked_up,
            "hit_rate": round((exact + near) / looked_up, 4) if looked_up else 0.0,
            "calls_avoided": exact + near,
        }
