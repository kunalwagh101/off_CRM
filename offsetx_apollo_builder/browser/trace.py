"""Every action the agent took, appended, never rewritten.

Three jobs from one artefact, which is why it is worth building properly rather
than logging as an afterthought:

**Audit.** An agent working in your logged-in session can do anything you can
do. "What did it actually do" must have a complete answer, and it must be an
answer nothing can quietly edit — so this is append-only and the file is opened
in append mode, never truncated.

**Resume.** A run is resumable *because* the trace is complete. Not "we save
progress every so often": the trace **is** the progress, so resuming is
replaying it into the context and continuing from the end.

**Watching it think.** The same records drive the live view. One artefact
serving both means the thing you watch and the thing you audit cannot disagree,
which they always eventually do when they are two systems.

---

**JSON Lines, not a database table.** A trace is written once and read in order;
that is exactly what a log file is good at, and it means a run's record is a
file the owner can open, grep, keep or delete without a query. Screenshots go
beside it as files, referenced by name, because a base64 PNG per step turns a
readable log into an unreadable one.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

#: What one step's detail may weigh in the log. A page's text can be enormous
#: and the trace is meant to stay readable; the full text lives in the step's
#: own artefact when it is needed.
MAX_DETAIL_CHARS = 4_000


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Step:
    """One thing that happened."""

    kind: str
    detail: str = ""
    url: str = ""
    ok: bool = True
    took_ms: int = 0
    #: Set for a model call, so a run's cost is the sum of its trace.
    provider_id: str = ""
    model_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    #: Estimated because not every provider exposes authoritative usage in the
    #: generation response. Exact provider-ledger reconciliation is S-06.01.03.
    estimated_cost_usd: float = 0.0
    #: Filename of a screenshot beside the log, when there is one.
    screenshot: str = ""
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        item = {"at": self.at, "kind": self.kind, "ok": self.ok}
        for key, value in (
            ("detail", self.detail[:MAX_DETAIL_CHARS]), ("url", self.url),
            ("provider_id", self.provider_id), ("model_id", self.model_id),
            ("screenshot", self.screenshot),
        ):
            if value:
                item[key] = value
        for key, number in (
            ("took_ms", self.took_ms), ("tokens_in", self.tokens_in),
            ("tokens_out", self.tokens_out),
        ):
            if number:
                item[key] = int(number)
        if self.estimated_cost_usd:
            item["estimated_cost_usd"] = round(float(self.estimated_cost_usd), 8)
        return item


@dataclass
class Trace:
    """The record of one run.

    Nothing here can remove a step. There is no `edit`, no `delete` and no
    `truncate`, and that is deliberate: an audit log with an eraser in it is not
    an audit log.
    """

    run_id: str
    directory: Path
    #: Kept in memory as well as on disk so a live view needs no re-read.
    steps: list[Step] = field(default_factory=list)

    @classmethod
    def open(cls, root: Path | str, *, run_id: str = "") -> "Trace":
        identifier = run_id or f"run_{uuid.uuid4().hex[:12]}"
        directory = Path(root) / identifier
        directory.mkdir(parents=True, exist_ok=True)
        # 0700: a trace holds screenshots of whatever the agent was looking at,
        # which on a logged-in session is your mail and your CRM.
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
        trace = cls(run_id=identifier, directory=directory)
        trace.steps = list(trace.read())
        return trace

    @property
    def path(self) -> Path:
        return self.directory / "trace.jsonl"

    def append(self, step: Step, *, screenshot: bytes = b"") -> Step:
        """Record one step. The only way anything enters a trace."""
        if screenshot:
            name = f"{len(self.steps):04d}.png"
            shot = self.directory / name
            shot.write_bytes(screenshot)
            try:
                os.chmod(shot, 0o600)
            except OSError:
                pass
            step.screenshot = name
        # Append mode, opened per write. Slower than holding a handle, and it
        # means a crashed process leaves a complete trace up to the last step
        # rather than a buffer nobody flushed.
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(step.to_dict(), ensure_ascii=False) + "\n")
        self.steps.append(step)
        return step

    def read(self) -> Iterator[Step]:
        """Replay the trace from disk. What resuming is built on."""
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                # A half-written last line after a hard kill. Everything before
                # it is still good, and stopping here is better than refusing
                # to read a trace because its final byte is missing.
                break
            yield Step(
                kind=str(raw.get("kind") or ""),
                detail=str(raw.get("detail") or ""),
                url=str(raw.get("url") or ""),
                ok=bool(raw.get("ok", True)),
                took_ms=int(raw.get("took_ms") or 0),
                provider_id=str(raw.get("provider_id") or ""),
                model_id=str(raw.get("model_id") or ""),
                tokens_in=int(raw.get("tokens_in") or 0),
                tokens_out=int(raw.get("tokens_out") or 0),
                estimated_cost_usd=float(raw.get("estimated_cost_usd") or 0.0),
                screenshot=str(raw.get("screenshot") or ""),
                at=str(raw.get("at") or ""),
            )

    def summary(self) -> dict[str, Any]:
        """What this run cost and how far it got."""
        return {
            "run_id": self.run_id,
            "steps": len(self.steps),
            "failed": len([step for step in self.steps if not step.ok]),
            "took_ms": sum(step.took_ms for step in self.steps),
            "tokens_in": sum(step.tokens_in for step in self.steps),
            "tokens_out": sum(step.tokens_out for step in self.steps),
            "estimated_cost_usd": round(
                sum(step.estimated_cost_usd for step in self.steps), 8
            ),
            "models": sorted({step.model_id for step in self.steps if step.model_id}),
            "started_at": self.steps[0].at if self.steps else "",
            "ended_at": self.steps[-1].at if self.steps else "",
        }

    def render(self, *, limit: int = 200) -> str:
        """The trace as text — for a person, and for replaying into a prompt."""
        lines = []
        for index, step in enumerate(self.steps[:limit]):
            mark = " " if step.ok else "!"
            lines.append(f"{mark}{index:3d}  {step.kind:<12} {step.detail}".rstrip())
        if len(self.steps) > limit:
            lines.append(f"… {len(self.steps) - limit} more steps")
        return "\n".join(lines)
