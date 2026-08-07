"""The scoreboard, and the champion/challenger gate.

This is what turns "orchestration is better" from a hope into a property.

The rule:

    champion   = the best single model measured on the suite
    challenger = a run mode (compare, orchestrated)

    the challenger is used ONLY IF it beats the champion by a margin that is
    unlikely to be noise. Otherwise traffic stays on the champion.

Under that rule the system cannot perform worse than the best single model,
because when the ensemble loses it does not get used.  That is a guarantee by
construction rather than an aspiration.

**Why a significance test and not ``>``.**  A suite has tens of cases, not
thousands.  Comparing two mean scores and shipping whichever is higher will flip
the winner on noise roughly half the time when the two are actually equal, and
each flip costs real money because the challenger runs several models per task.
Both subjects run the *same* cases, so the comparison is paired, and the honest
test for paired data is a sign test: count the cases each side wins and ask how
likely that split is from a coin.  It is exact, needs no dependencies, and makes
no assumption about how scores are distributed.

Two safety rules, matching ``ai/context.py``:

* **No model can read or write this store.**  There is no query interface, no
  tool, no provider import.  A scoreboard a model could edit is a scoreboard
  that tells you what the model wants you to hear.
* **Only code writes here.**  Every number comes from a deterministic check.
"""
from __future__ import annotations

import json
import math
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..outreach.models import to_utc_iso
from .evals import EvalReport

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_eval_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    suite_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0.0,
    cases INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    per_case TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eval_runs_lookup
    ON ai_eval_runs(workspace_id, suite_id, subject, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_champions (
    workspace_id TEXT NOT NULL DEFAULT 'local',
    suite_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    subject_kind TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0.0,
    decided_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (workspace_id, suite_id)
);
"""

#: How unlikely a win must be under "the two are equal" before we believe it.
DEFAULT_ALPHA = 0.05

#: A challenger that runs several models per task costs more.  Even a real win
#: is not worth an unbounded bill, so it must also stay under this multiple of
#: the champion's case count.  1 model vs 3 models is 3.0.
DEFAULT_MAX_COST_MULTIPLE = 4.0


def sign_test_p_value(wins: int, losses: int) -> float:
    """One-sided exact binomial probability of ``wins`` or more out of the
    decided cases, if the two subjects were truly equal.

    Ties are excluded, which is the standard treatment: a case both sides score
    identically carries no information about which is better.

    Returns 1.0 when nothing is decided, so "no evidence" can never look like
    "significant".
    """
    decided = wins + losses
    if decided <= 0:
        return 1.0
    tail = sum(math.comb(decided, k) for k in range(wins, decided + 1))
    return tail / (2**decided)


@dataclass(slots=True)
class Verdict:
    """Why the challenger did or did not take over."""

    suite_id: str
    champion: str
    champion_score: float
    challenger: str
    challenger_score: float
    wins: int
    losses: int
    ties: int
    p_value: float
    cost_multiple: float
    promoted: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "champion": self.champion,
            "champion_score": round(self.champion_score, 4),
            "challenger": self.challenger,
            "challenger_score": round(self.challenger_score, 4),
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "p_value": round(self.p_value, 5),
            "cost_multiple": round(self.cost_multiple, 2),
            "promoted": self.promoted,
            "reason": self.reason,
        }


def compare(
    champion: EvalReport,
    challenger: EvalReport,
    *,
    alpha: float = DEFAULT_ALPHA,
    max_cost_multiple: float = DEFAULT_MAX_COST_MULTIPLE,
    cost_multiple: float = 1.0,
) -> Verdict:
    """Paired comparison of two reports over the same suite.

    Promotion needs three things, all of them:

    1. a higher mean score — a challenger that wins more cases but loses the
       ones it loses badly has not improved the output the owner actually reads;
    2. a case-level win margin unlikely under chance;
    3. a cost that stays inside the ceiling.

    Anything else keeps the champion.  The default is always "do not change" —
    the same fail-closed instinct the egress gate uses.
    """
    if champion.suite_id != challenger.suite_id:
        raise ValueError(
            f"Cannot compare across suites: {champion.suite_id!r} vs {challenger.suite_id!r}"
        )

    champ_cases = champion.score_by_case()
    chall_cases = challenger.score_by_case()
    shared = sorted(set(champ_cases) & set(chall_cases))
    if not shared:
        return Verdict(
            suite_id=champion.suite_id,
            champion=champion.subject,
            champion_score=champion.score,
            challenger=challenger.subject,
            challenger_score=challenger.score,
            wins=0,
            losses=0,
            ties=0,
            p_value=1.0,
            cost_multiple=cost_multiple,
            promoted=False,
            reason=(
                "The two runs share no cases, so there is nothing to compare. "
                "Run both against the same suite."
            ),
        )

    wins = sum(1 for c in shared if chall_cases[c] > champ_cases[c])
    losses = sum(1 for c in shared if chall_cases[c] < champ_cases[c])
    ties = len(shared) - wins - losses
    p_value = sign_test_p_value(wins, losses)

    def verdict(promoted: bool, reason: str) -> Verdict:
        return Verdict(
            suite_id=champion.suite_id,
            champion=champion.subject,
            champion_score=champion.score,
            challenger=challenger.subject,
            challenger_score=challenger.score,
            wins=wins,
            losses=losses,
            ties=ties,
            p_value=p_value,
            cost_multiple=cost_multiple,
            promoted=promoted,
            reason=reason,
        )

    if challenger.score <= champion.score:
        return verdict(
            False,
            f"{challenger.subject} scored {challenger.score:.3f} against "
            f"{champion.subject} at {champion.score:.3f}. Not an improvement, so "
            "traffic stays on the single model.",
        )
    if cost_multiple > max_cost_multiple:
        return verdict(
            False,
            f"{challenger.subject} scored higher but costs {cost_multiple:.1f}x the "
            f"champion, over the {max_cost_multiple:.1f}x ceiling. Raise the ceiling "
            "deliberately if the quality is worth it.",
        )
    if p_value > alpha:
        return verdict(
            False,
            f"{challenger.subject} won {wins} cases and lost {losses} of "
            f"{len(shared)}. With this few cases that split has a "
            f"{p_value:.0%} chance of being luck, above the {alpha:.0%} bar. "
            "Add cases or accept the champion.",
        )
    return verdict(
        True,
        f"{challenger.subject} won {wins} and lost {losses} of {len(shared)} cases "
        f"(p={p_value:.3f}), scoring {challenger.score:.3f} against "
        f"{champion.score:.3f}, at {cost_multiple:.1f}x cost. Promoted.",
    )


def best_of(reports: Sequence[EvalReport]) -> EvalReport | None:
    """The champion: highest mean score, ties broken by speed."""
    if not reports:
        return None
    return sorted(reports, key=lambda r: (-r.score, r.duration_ms))[0]


class Scoreboard:
    """Stores eval runs and the current champion per suite.

    SQLite, like the rest of off_CRM's storage, behind the same kind of boundary
    so a move to Postgres is a swap rather than a rewrite.
    """

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
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

    # ── recording ───────────────────────────────────────────────────────────

    def record(self, report: EvalReport, *, workspace_id: str = "local") -> str:
        """Store one run.  Returns its id."""
        run_id = uuid.uuid4().hex
        with self._lock, self.connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_eval_runs
                    (id, workspace_id, suite_id, subject, subject_kind, score,
                     cases, errors, duration_ms, per_case, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    workspace_id,
                    report.suite_id,
                    report.subject,
                    report.subject_kind,
                    report.score,
                    len(report.results),
                    report.errors,
                    report.duration_ms,
                    json.dumps(report.score_by_case()),
                    to_utc_iso(),
                ),
            )
        return run_id

    def history(
        self,
        *,
        workspace_id: str = "local",
        suite_id: str = "",
        subject: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM ai_eval_runs WHERE workspace_id = ?"
        params: list[Any] = [workspace_id]
        if suite_id:
            sql += " AND suite_id = ?"
            params.append(suite_id)
        if subject:
            sql += " AND subject = ?"
            params.append(subject)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "suite_id": row["suite_id"],
                "subject": row["subject"],
                "subject_kind": row["subject_kind"],
                "score": row["score"],
                "cases": row["cases"],
                "errors": row["errors"],
                "duration_ms": row["duration_ms"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def leaderboard(
        self, *, workspace_id: str = "local", suite_id: str
    ) -> list[dict[str, Any]]:
        """Latest score per subject, best first — what the UI shows."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT subject, subject_kind, score, cases, errors, created_at
                FROM ai_eval_runs r
                WHERE workspace_id = ? AND suite_id = ?
                  AND created_at = (
                      SELECT MAX(created_at) FROM ai_eval_runs
                      WHERE workspace_id = r.workspace_id
                        AND suite_id = r.suite_id
                        AND subject = r.subject
                  )
                ORDER BY score DESC, subject ASC
                """,
                (workspace_id, suite_id),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── the champion ────────────────────────────────────────────────────────

    def set_champion(
        self,
        *,
        workspace_id: str = "local",
        suite_id: str,
        subject: str,
        subject_kind: str,
        score: float,
        reason: str = "",
    ) -> None:
        with self._lock, self.connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_champions
                    (workspace_id, suite_id, subject, subject_kind, score, decided_at, reason)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(workspace_id, suite_id) DO UPDATE SET
                    subject=excluded.subject,
                    subject_kind=excluded.subject_kind,
                    score=excluded.score,
                    decided_at=excluded.decided_at,
                    reason=excluded.reason
                """,
                (
                    workspace_id,
                    suite_id,
                    subject,
                    subject_kind,
                    float(score),
                    to_utc_iso(),
                    reason,
                ),
            )

    def champion(
        self, *, workspace_id: str = "local", suite_id: str
    ) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM ai_champions WHERE workspace_id = ? AND suite_id = ?",
                (workspace_id, suite_id),
            ).fetchone()
        return dict(row) if row else None

    def route_for(
        self, *, workspace_id: str = "local", suite_id: str, default: str = "simple"
    ) -> str:
        """What the router should use for this kind of task.

        Falls back to ``simple`` when nothing has been measured.  An unmeasured
        system routes to one model, which is the cheap and safe default — never
        to an ensemble nobody has checked.
        """
        current = self.champion(workspace_id=workspace_id, suite_id=suite_id)
        if not current:
            return default
        return str(current["subject"]) if current["subject_kind"] == "mode" else default

    def stats(self, *, workspace_id: str = "local") -> dict[str, Any]:
        with self.connection() as conn:
            runs = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_eval_runs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
            suites = conn.execute(
                "SELECT COUNT(DISTINCT suite_id) AS n FROM ai_eval_runs WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
            champions = conn.execute(
                "SELECT COUNT(*) AS n FROM ai_champions WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()["n"]
        return {"runs": runs, "suites": suites, "champions": champions}
