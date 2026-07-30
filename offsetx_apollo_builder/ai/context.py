"""The context layer.

This is the part that remembers. It sits between the CRM and the AI models and
does three jobs:

1. **Keeps the job's place.** What are we doing, which steps are done, what did
   the owner decide. So swapping from one model to another mid-job does not
   start from nothing.

2. **Counts what works.** How many emails each template sent, how many replies
   came back. Plain counting. No AI involved.

3. **Holds the winning template.** The best-performing template becomes the
   reference other models are shown: "this one works, use it or beat it."

Two rules make this safe, and both are tested:

* **No model can read this store.** It has no query interface, no retrieval
  tool, no connection a provider could use. off_CRM reads it and builds a
  payload; a model only ever receives that payload.
* **Only code writes here.** Every field is written by Python, never extracted
  by an AI. That keeps the numbers honest and removes the per-write AI cost
  that memory frameworks usually carry.

On learning: this is **not** fine-tuning. Nothing is sent away to retrain a
model. A weak template is rewritten by sending only two things — the template
text and a reply-rate number. No names, no addresses, no recipients.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..outreach.models import to_utc_iso
from .payload import EgressRequest
from .tiers import DataClass

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_task_state (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    kind TEXT NOT NULL DEFAULT 'campaign',
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    steps TEXT NOT NULL DEFAULT '[]',
    decisions TEXT NOT NULL DEFAULT '[]',
    facts TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_task_state_open
    ON ai_task_state(workspace_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_template_stats (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    template_id TEXT NOT NULL,
    variant_id TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL DEFAULT '',
    template_text TEXT NOT NULL DEFAULT '',
    sends INTEGER NOT NULL DEFAULT 0,
    replies INTEGER NOT NULL DEFAULT 0,
    is_winner INTEGER NOT NULL DEFAULT 0,
    retired INTEGER NOT NULL DEFAULT 0,
    parent_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, template_id, variant_id)
);
CREATE INDEX IF NOT EXISTS ix_template_stats_workspace
    ON ai_template_stats(workspace_id, retired, sends DESC);
"""

#: A template needs at least this many sends before its reply rate means
#: anything. Below it, one lucky reply looks like a 100% success rate.
MIN_SENDS_TO_JUDGE = 20

#: At or below this reply rate (percent), a template is worth rewriting.
WEAK_REPLY_RATE = 5.0

#: How many recent events the rolling summary keeps. Enough to carry the thread,
#: small enough that it never becomes a large payload.
SUMMARY_EVENTS = 12


@dataclass(slots=True)
class TaskState:
    """Where a job has got to."""

    id: str
    workspace_id: str
    kind: str
    title: str
    status: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def done_count(self) -> int:
        return sum(1 for step in self.steps if step.get("status") == "done")

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def next_step(self) -> dict[str, Any] | None:
        return next((step for step in self.steps if step.get("status") != "done"), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "steps": self.steps,
            "decisions": self.decisions,
            "facts": self.facts,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "done_count": self.done_count,
            "total_steps": self.total_steps,
            "next_step": self.next_step,
        }


@dataclass(slots=True)
class TemplateScore:
    """How one template is performing."""

    id: str
    template_id: str
    variant_id: str
    label: str
    sends: int
    replies: int
    is_winner: bool
    retired: bool
    parent_id: str = ""
    template_text: str = ""

    @property
    def reply_rate(self) -> float:
        return round(self.replies / self.sends * 100, 1) if self.sends else 0.0

    @property
    def judged(self) -> bool:
        """True once there are enough sends for the rate to mean something."""
        return self.sends >= MIN_SENDS_TO_JUDGE

    @property
    def weak(self) -> bool:
        return self.judged and self.reply_rate <= WEAK_REPLY_RATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "template_id": self.template_id,
            "variant_id": self.variant_id,
            "label": self.label,
            "sends": self.sends,
            "replies": self.replies,
            "reply_rate": self.reply_rate,
            "is_winner": self.is_winner,
            "retired": self.retired,
            "parent_id": self.parent_id,
            "judged": self.judged,
            "weak": self.weak,
            "min_sends_to_judge": MIN_SENDS_TO_JUDGE,
        }


class ContextLayer:
    """Remembers where a job is, and which templates earn replies.

    Owns its own SQLite tables and connection, like the egress log, so the AI
    module stays liftable into its own repository.
    """

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._connection is None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                connection = sqlite3.connect(
                    self.path, check_same_thread=False, isolation_level=None
                )
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA busy_timeout=5000")
                connection.executescript(SCHEMA)
                self._connection = connection
            return self._connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    # ── job 1: keep the job's place ─────────────────────────────────────────

    def start_task(
        self,
        *,
        workspace_id: str = "local",
        kind: str = "campaign",
        title: str = "",
        steps: list[str] | None = None,
    ) -> TaskState:
        now = to_utc_iso()
        task = TaskState(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            kind=kind,
            title=title[:200],
            status="open",
            steps=[
                {"index": index, "name": str(name)[:200], "status": "pending", "note": ""}
                for index, name in enumerate(steps or [])
            ],
            created_at=now,
            updated_at=now,
        )
        task.summary = self._build_summary(task)
        self._write(task)
        return task

    def get_task(self, task_id: str) -> TaskState | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM ai_task_state WHERE id = ?", (task_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def open_tasks(self, workspace_id: str = "local", limit: int = 20) -> list[TaskState]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM ai_task_state WHERE workspace_id = ? AND status = 'open'"
                " ORDER BY updated_at DESC LIMIT ?",
                (workspace_id, max(1, min(limit, 100))),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def finish_step(
        self, task_id: str, step_index: int, *, note: str = "", status: str = "done"
    ) -> TaskState | None:
        """Mark a step done. Written by code — never by a model."""
        task = self.get_task(task_id)
        if task is None:
            return None
        for step in task.steps:
            if int(step.get("index", -1)) == step_index:
                step["status"] = status
                step["note"] = str(note)[:500]
                step["at"] = to_utc_iso()
        task.summary = self._build_summary(task)
        task.updated_at = to_utc_iso()
        self._write(task)
        return task

    def record_decision(self, task_id: str, decision: str, *, made_by: str = "owner") -> TaskState | None:
        """Remember a choice, so a later model does not undo it."""
        task = self.get_task(task_id)
        if task is None:
            return None
        task.decisions.append(
            {"text": str(decision)[:500], "made_by": made_by, "at": to_utc_iso()}
        )
        task.decisions = task.decisions[-50:]
        task.summary = self._build_summary(task)
        task.updated_at = to_utc_iso()
        self._write(task)
        return task

    def remember_fact(self, task_id: str, key: str, value: Any) -> TaskState | None:
        """Store a plain fact about the job. Structured field, written by code."""
        task = self.get_task(task_id)
        if task is None:
            return None
        task.facts[str(key)[:80]] = value
        task.summary = self._build_summary(task)
        task.updated_at = to_utc_iso()
        self._write(task)
        return task

    def close_task(self, task_id: str, *, status: str = "done") -> TaskState | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        task.status = status
        task.updated_at = to_utc_iso()
        self._write(task)
        return task

    @staticmethod
    def _build_summary(task: TaskState) -> str:
        """A few plain lines a model can be *given* — never one it can query.

        Deterministic: assembled by this function from stored fields, not written
        by an AI. That is what keeps it free and keeps the numbers honest.
        """
        lines = [f"Job: {task.title or task.kind}"]
        if task.steps:
            lines.append(f"Progress: {task.done_count} of {task.total_steps} steps done.")
            nxt = task.next_step
            if nxt:
                lines.append(f"Next: {nxt.get('name', '')}")
        for decision in task.decisions[-SUMMARY_EVENTS:]:
            lines.append(f"Decided: {decision.get('text', '')}")
        for key, value in list(task.facts.items())[:SUMMARY_EVENTS]:
            lines.append(f"{key}: {value}")
        return "\n".join(lines)[:4000]

    def _write(self, task: TaskState) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO ai_task_state("
                " id, workspace_id, kind, title, status, steps, decisions, facts,"
                " summary, created_at, updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET"
                " kind=excluded.kind, title=excluded.title, status=excluded.status,"
                " steps=excluded.steps, decisions=excluded.decisions,"
                " facts=excluded.facts, summary=excluded.summary,"
                " updated_at=excluded.updated_at",
                (
                    task.id,
                    task.workspace_id,
                    task.kind,
                    task.title,
                    task.status,
                    json.dumps(task.steps, ensure_ascii=False),
                    json.dumps(task.decisions, ensure_ascii=False),
                    json.dumps(task.facts, ensure_ascii=False, default=str),
                    task.summary,
                    task.created_at,
                    task.updated_at,
                ),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> TaskState:
        def load(value: Any, fallback: Any) -> Any:
            try:
                return json.loads(str(value))
            except (TypeError, ValueError):
                return fallback

        return TaskState(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            kind=str(row["kind"]),
            title=str(row["title"]),
            status=str(row["status"]),
            steps=load(row["steps"], []),
            decisions=load(row["decisions"], []),
            facts=load(row["facts"], {}),
            summary=str(row["summary"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    # ── job 2: count what works ─────────────────────────────────────────────

    def register_template(
        self,
        *,
        workspace_id: str = "local",
        template_id: str,
        variant_id: str = "",
        label: str = "",
        template_text: str = "",
        parent_id: str = "",
    ) -> TemplateScore:
        now = to_utc_iso()
        row_id = str(uuid.uuid4())
        with self._lock:
            self.connection.execute(
                "INSERT INTO ai_template_stats("
                " id, workspace_id, template_id, variant_id, label, template_text,"
                " parent_id, created_at, updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(workspace_id, template_id, variant_id) DO UPDATE SET"
                " label=excluded.label, template_text=excluded.template_text,"
                " updated_at=excluded.updated_at",
                (
                    row_id,
                    workspace_id,
                    template_id,
                    variant_id,
                    label[:200],
                    template_text[:12000],
                    parent_id,
                    now,
                    now,
                ),
            )
        score = self.score_for(workspace_id, template_id, variant_id)
        assert score is not None  # just written
        return score

    def record_send(
        self, *, workspace_id: str = "local", template_id: str, variant_id: str = ""
    ) -> None:
        """One email went out. Counting, not judging."""
        self._bump(workspace_id, template_id, variant_id, "sends")

    def record_reply(
        self, *, workspace_id: str = "local", template_id: str, variant_id: str = ""
    ) -> None:
        """One reply came back.

        The caller detects the reply without a model — arrival is a fact, not an
        opinion. The reply's *content* never reaches this store or any provider.
        """
        self._bump(workspace_id, template_id, variant_id, "replies")

    def _bump(self, workspace_id: str, template_id: str, variant_id: str, column: str) -> None:
        if column not in {"sends", "replies"}:
            raise ValueError("Only sends and replies are counted here")
        now = to_utc_iso()
        with self._lock:
            self.connection.execute(
                "INSERT INTO ai_template_stats("
                f" id, workspace_id, template_id, variant_id, {column}, created_at, updated_at"
                ") VALUES(?,?,?,?,1,?,?)"
                " ON CONFLICT(workspace_id, template_id, variant_id) DO UPDATE SET"
                f" {column} = {column} + 1, updated_at = excluded.updated_at",
                (str(uuid.uuid4()), workspace_id, template_id, variant_id, now, now),
            )

    def score_for(
        self, workspace_id: str, template_id: str, variant_id: str = ""
    ) -> TemplateScore | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT * FROM ai_template_stats"
                " WHERE workspace_id = ? AND template_id = ? AND variant_id = ?",
                (workspace_id, template_id, variant_id),
            ).fetchone()
        return self._score_from_row(row) if row else None

    def scoreboard(
        self, workspace_id: str = "local", *, include_retired: bool = False
    ) -> list[TemplateScore]:
        """Best reply rate first, then most sends."""
        clause = "" if include_retired else " AND retired = 0"
        with self._lock:
            rows = self.connection.execute(
                f"SELECT * FROM ai_template_stats WHERE workspace_id = ?{clause}",
                (workspace_id,),
            ).fetchall()
        scores = [self._score_from_row(row) for row in rows]
        scores.sort(key=lambda item: (-item.reply_rate, -item.sends))
        return scores

    def weak_templates(self, workspace_id: str = "local") -> list[TemplateScore]:
        """Templates with enough sends to judge, and a poor reply rate."""
        return [score for score in self.scoreboard(workspace_id) if score.weak]

    def winner(self, workspace_id: str = "local") -> TemplateScore | None:
        """The best template that has been sent enough times to trust."""
        judged = [score for score in self.scoreboard(workspace_id) if score.judged]
        return judged[0] if judged else None

    def mark_winner(self, workspace_id: str, template_id: str, variant_id: str = "") -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE ai_template_stats SET is_winner = 0 WHERE workspace_id = ?",
                (workspace_id,),
            )
            self.connection.execute(
                "UPDATE ai_template_stats SET is_winner = 1, updated_at = ?"
                " WHERE workspace_id = ? AND template_id = ? AND variant_id = ?",
                (to_utc_iso(), workspace_id, template_id, variant_id),
            )

    def retire(self, workspace_id: str, template_id: str, variant_id: str = "") -> None:
        with self._lock:
            self.connection.execute(
                "UPDATE ai_template_stats SET retired = 1, updated_at = ?"
                " WHERE workspace_id = ? AND template_id = ? AND variant_id = ?",
                (to_utc_iso(), workspace_id, template_id, variant_id),
            )

    @staticmethod
    def _score_from_row(row: sqlite3.Row) -> TemplateScore:
        return TemplateScore(
            id=str(row["id"]),
            template_id=str(row["template_id"]),
            variant_id=str(row["variant_id"]),
            label=str(row["label"]),
            sends=int(row["sends"]),
            replies=int(row["replies"]),
            is_winner=bool(row["is_winner"]),
            retired=bool(row["retired"]),
            parent_id=str(row["parent_id"]),
            template_text=str(row["template_text"]),
        )

    # ── job 3: rewrite a weak template, and share the winner ────────────────

    def rewrite_request(
        self, score: TemplateScore, *, winner: TemplateScore | None = None
    ) -> EgressRequest:
        """Build the payload that asks a model to improve a weak template.

        This is the whole learning loop, and note what it contains: the template
        text, two numbers, and optionally the winning template as a reference.

        No recipient. No name. No address. No campaign. Nothing about any real
        person — so the data class is ``public`` and any permitted model can do
        it. This is why the loop costs almost nothing and leaks nothing.

        It is also not fine-tuning: no data is sent away to retrain anything.
        """
        lines = [
            "Rewrite this outreach email template so more people reply.",
            "",
            f"It was sent {score.sends} times and got {score.replies} replies "
            f"({score.reply_rate}%).",
            "",
            "Current template:",
            score.template_text or "(no text stored)",
        ]
        if winner is not None and winner.id != score.id and winner.template_text:
            lines += [
                "",
                f"For reference, this template earns {winner.reply_rate}% replies. "
                "Use what works in it, or do better:",
                winner.template_text,
            ]
        lines += [
            "",
            "Keep any {{placeholder}} markers exactly as they are.",
            "Return only the new template text.",
        ]
        return EgressRequest(
            task_type="template_rewrite",
            data_class=DataClass.PUBLIC,
            instructions="\n".join(lines),
            task_tags=("writing",),
        )

    def reference_for_models(self, workspace_id: str = "local") -> str:
        """The winning template, as a line other models can be shown.

        The owner asked for this: the context layer keeps the best template and
        offers it to other models as a reference they may follow or beat.
        """
        best = self.winner(workspace_id)
        if best is None or not best.template_text:
            return ""
        return (
            f"This template currently earns {best.reply_rate}% replies over "
            f"{best.sends} sends. You may follow it or write something better:\n"
            f"{best.template_text}"
        )

    def stats(self, workspace_id: str = "local") -> dict[str, Any]:
        scores = self.scoreboard(workspace_id)
        best = self.winner(workspace_id)
        return {
            "templates": len(scores),
            "total_sends": sum(score.sends for score in scores),
            "total_replies": sum(score.replies for score in scores),
            "judged": sum(1 for score in scores if score.judged),
            "weak": len([score for score in scores if score.weak]),
            "winner": best.to_dict() if best else None,
            "open_tasks": len(self.open_tasks(workspace_id)),
            "min_sends_to_judge": MIN_SENDS_TO_JUDGE,
            "weak_reply_rate": WEAK_REPLY_RATE,
        }
