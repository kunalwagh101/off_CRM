"""One-shot, assertion-backed source transform for S-06.02.03.

This file exists only because the repository connector exposes whole-file writes,
not patch application. The workflow that invokes it deletes it before committing
the product change. Every replacement asserts its exact old source exists once;
if the repository moved, it fails closed instead of guessing.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one patch anchor, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


RUN = "offsetx_apollo_builder/agent/run.py"

replace_once(
    RUN,
    '''    spend_ceiling_usd: float = 0.0\n\n    @property\n    def steps_remaining(self) -> int:\n''',
    '''    spend_ceiling_usd: float = 0.0\n    #: Cumulative measured execution latency allowed for this run. `S-06.02.03`\n    #:\n    #: Zero means uncapped. It is persisted and re-applied on resume so a restart\n    #: cannot mint a fresh latency allowance.\n    latency_ceiling_ms: int = 0\n\n    @property\n    def steps_remaining(self) -> int:\n''',
)

replace_once(
    RUN,
    '''        spend_ceiling_usd=float(parameters.get("spend_ceiling_usd") or 0.0),\n        schema_fields=tuple(str(f) for f in (parameters.get("result_schema") or ())),\n''',
    '''        spend_ceiling_usd=float(parameters.get("spend_ceiling_usd") or 0.0),\n        latency_ceiling_ms=int(parameters.get("latency_ceiling_ms") or 0),\n        schema_fields=tuple(str(f) for f in (parameters.get("result_schema") or ())),\n''',
)

replace_once(
    RUN,
    '''def estimate_run(model: Any, *, step_budget: int, model_id: str = "") -> RunEstimate:\n''',
    '''def latency_ceiling_reached(*, ceiling_ms: int, spent_ms: int) -> bool:\n    """Whether another unit of work may start.  `S-06.02.03`\n\n    Latency cannot be predicted safely the way token spend can. The run therefore\n    lets an operation already in flight finish, records its measured latency, and\n    refuses to start anything else once the ceiling has been reached. Zero means\n    uncapped.\n    """\n    if ceiling_ms <= 0:\n        return False\n    return spent_ms >= ceiling_ms\n\n\ndef estimate_run(model: Any, *, step_budget: int, model_id: str = "") -> RunEstimate:\n''',
)

replace_once(
    RUN,
    '''    #: What the run was allowed to spend. Zero means it was not capped.  `S-11.01.04`\n    spend_ceiling_usd: float = 0.0\n\n    @property\n    def headroom_usd(self) -> float:\n        """What was left of the ceiling. Zero when there was no ceiling."""\n        if self.spend_ceiling_usd <= 0:\n            return 0.0\n        return self.spend_ceiling_usd - self.spend_usd\n\n    @property\n    def spend_usd(self) -> float:\n        return float(self.trace_summary.get("estimated_cost_usd", 0.0) or 0.0)\n''',
    '''    #: What the run was allowed to spend. Zero means it was not capped.  `S-11.01.04`\n    spend_ceiling_usd: float = 0.0\n    #: Cumulative measured execution latency allowed for the run. `S-06.02.03`\n    latency_ceiling_ms: int = 0\n\n    @property\n    def headroom_usd(self) -> float:\n        """What was left of the ceiling. Zero when there was no ceiling."""\n        if self.spend_ceiling_usd <= 0:\n            return 0.0\n        return self.spend_ceiling_usd - self.spend_usd\n\n    @property\n    def spend_usd(self) -> float:\n        return float(self.trace_summary.get("estimated_cost_usd", 0.0) or 0.0)\n\n    @property\n    def latency_ms(self) -> int:\n        """Measured provider + browser latency recorded by the append-only trace."""\n        return int(self.trace_summary.get("took_ms", 0) or 0)\n\n    @property\n    def latency_headroom_ms(self) -> int:\n        """Unused latency budget; zero once the ceiling has been reached."""\n        if self.latency_ceiling_ms <= 0:\n            return 0\n        return max(0, self.latency_ceiling_ms - self.latency_ms)\n\n    @property\n    def latency_overrun_ms(self) -> int:\n        """How far the already-in-flight operation crossed the latency ceiling."""\n        if self.latency_ceiling_ms <= 0:\n            return 0\n        return max(0, self.latency_ms - self.latency_ceiling_ms)\n''',
)

replace_once(
    RUN,
    '''            "headroom_usd": round(self.headroom_usd, 8),\n            "estimate_error_usd": round(self.estimate_error, 8),\n''',
    '''            "headroom_usd": round(self.headroom_usd, 8),\n            "estimate_error_usd": round(self.estimate_error, 8),\n            "latency_ms": self.latency_ms,\n            "latency_ceiling_ms": self.latency_ceiling_ms,\n            "latency_headroom_ms": self.latency_headroom_ms,\n            "latency_overrun_ms": self.latency_overrun_ms,\n''',
)

replace_once(
    RUN,
    '''        on_progress: "Callable[[Progress], None] | None" = None,\n        spend_ceiling_usd: float = 0.0,\n    ) -> RunOutcome:\n''',
    '''        on_progress: "Callable[[Progress], None] | None" = None,\n        spend_ceiling_usd: float = 0.0,\n        latency_ceiling_ms: int = 0,\n    ) -> RunOutcome:\n''',
)

replace_once(
    RUN,
    '''        `spend_ceiling_usd` caps what the run may spend. The check happens\n        *before* each decision is asked for, so the ceiling is never crossed\n        rather than noticed afterwards; zero means no ceiling.  `S-11.01.04`\n\n        `on_progress` is called with each step as it is recorded, so a run can\n''',
    '''        `spend_ceiling_usd` caps what the run may spend. The check happens\n        *before* each decision is asked for, so the ceiling is never crossed\n        rather than noticed afterwards; zero means no ceiling.  `S-11.01.04`\n\n        `latency_ceiling_ms` caps cumulative measured provider/browser latency.\n        An operation already in flight is allowed to finish rather than being\n        cancelled halfway through a possible side effect; once its measured\n        latency reaches the ceiling, no new work starts. Zero means uncapped.\n        `S-06.02.03`\n\n        `on_progress` is called with each step as it is recorded, so a run can\n''',
)

replace_once(
    RUN,
    '''        cleaned_goal, budget = _validate_start(goal, step_budget)\n        schema = coerce_result_schema(result_schema)\n''',
    '''        cleaned_goal, budget = _validate_start(goal, step_budget)\n        latency_ceiling = _validate_latency_ceiling(latency_ceiling_ms)\n        schema = coerce_result_schema(result_schema)\n''',
)

replace_once(
    RUN,
    '''                cleaned_goal, budget, schema, resume_from, spend_ceiling_usd,\n            )\n''',
    '''                cleaned_goal, budget, schema, resume_from, spend_ceiling_usd,\n                latency_ceiling,\n            )\n''',
)

replace_once(
    RUN,
    '''        resume_from: "ResumeState | None",\n        spend_ceiling_usd: float = 0.0,\n    ) -> RunOutcome:\n''',
    '''        resume_from: "ResumeState | None",\n        spend_ceiling_usd: float = 0.0,\n        latency_ceiling_ms: int = 0,\n    ) -> RunOutcome:\n''',
)

replace_once(
    RUN,
    '''        self._estimate: RunEstimate | None = None\n        self._spend_ceiling_usd: float = float(spend_ceiling_usd)\n''',
    '''        self._estimate: RunEstimate | None = None\n        self._spend_ceiling_usd: float = float(spend_ceiling_usd)\n        self._latency_ceiling_ms: int = int(latency_ceiling_ms)\n''',
)

replace_once(
    RUN,
    '''        ceiling_note = ""\n        if spend_ceiling_usd > 0:\n            ceiling_note = f"spend_ceiling=${spend_ceiling_usd:.4f}; "\n            if estimate.projected_cost_usd > spend_ceiling_usd:\n                ceiling_note += (\n                    f"WARNING the projection (${estimate.projected_cost_usd:.4f}) "\n                    "is already above that ceiling, so this run is expected to "\n                    "stop short; "\n                )\n\n        schema_note = f"; result_schema={list(schema.fields)!r}" if schema else ""\n''',
    '''        ceiling_note = ""\n        if spend_ceiling_usd > 0:\n            ceiling_note = f"spend_ceiling=${spend_ceiling_usd:.4f}; "\n            if estimate.projected_cost_usd > spend_ceiling_usd:\n                ceiling_note += (\n                    f"WARNING the projection (${estimate.projected_cost_usd:.4f}) "\n                    "is already above that ceiling, so this run is expected to "\n                    "stop short; "\n                )\n        if latency_ceiling_ms > 0:\n            ceiling_note += f"latency_ceiling={latency_ceiling_ms}ms; "\n\n        schema_note = f"; result_schema={list(schema.fields)!r}" if schema else ""\n''',
)

replace_once(
    RUN,
    '''                "spend_ceiling_usd": round(float(spend_ceiling_usd), 8),\n            }),\n''',
    '''                "spend_ceiling_usd": round(float(spend_ceiling_usd), 8),\n                "latency_ceiling_ms": int(latency_ceiling_ms),\n            }),\n''',
)

replace_once(
    RUN,
    '''        for index in range(budget):\n            snapshot = await self.page.snapshot()\n''',
    '''        for index in range(budget):\n            latency_ms = int(self.trace.summary().get("took_ms", 0) or 0)\n            if latency_ceiling_reached(\n                ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms\n            ):\n                return self._over_latency(\n                    cleaned_goal, budget, decisions, actions, schema, collected,\n                    ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms,\n                )\n\n            snapshot = await self.page.snapshot()\n''',
)

replace_once(
    RUN,
    '''            self.trace.append(\n                Step(\n                    kind="decision",\n                    detail=_decision_detail(decision),\n                    url=snapshot.url,\n                    took_ms=result.duration_ms,\n                    provider_id=result.provider_id,\n                    model_id=result.model_id,\n                    tokens_in=tokens_in,\n                    tokens_out=tokens_out,\n                    estimated_cost_usd=estimated_cost,\n                )\n            )\n\n            validation: SourcedRecordValidation | None = None\n''',
    '''            self.trace.append(\n                Step(\n                    kind="decision",\n                    detail=_decision_detail(decision),\n                    url=snapshot.url,\n                    took_ms=result.duration_ms,\n                    provider_id=result.provider_id,\n                    model_id=result.model_id,\n                    tokens_in=tokens_in,\n                    tokens_out=tokens_out,\n                    estimated_cost_usd=estimated_cost,\n                )\n            )\n\n            latency_ms = int(self.trace.summary().get("took_ms", 0) or 0)\n            if latency_ceiling_reached(\n                ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms\n            ):\n                return self._over_latency(\n                    cleaned_goal, budget, decisions, actions, schema, collected,\n                    ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms,\n                )\n\n            validation: SourcedRecordValidation | None = None\n''',
)

replace_once(
    RUN,
    '''            observation = _observation(\n                action_result,\n                evidence_step=evidence_step,\n                evidence_error=evidence_error,\n            )\n\n        message = (\n''',
    '''            observation = _observation(\n                action_result,\n                evidence_step=evidence_step,\n                evidence_error=evidence_error,\n            )\n\n            latency_ms = int(self.trace.summary().get("took_ms", 0) or 0)\n            if latency_ceiling_reached(\n                ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms\n            ):\n                return self._over_latency(\n                    cleaned_goal, budget, decisions, actions, schema, collected,\n                    ceiling_ms=latency_ceiling_ms, spent_ms=latency_ms,\n                )\n\n        message = (\n''',
)

replace_once(
    RUN,
    '''    async def resume(self, *, spend_ceiling_usd: float | None = None) -> RunOutcome:\n''',
    '''    async def resume(\n        self,\n        *,\n        spend_ceiling_usd: float | None = None,\n        latency_ceiling_ms: int | None = None,\n    ) -> RunOutcome:\n''',
)

replace_once(
    RUN,
    '''            spend_ceiling_usd=(\n                state.spend_ceiling_usd if spend_ceiling_usd is None\n                else float(spend_ceiling_usd)\n            ),\n        )\n\n    def _over_budget(\n''',
    '''            spend_ceiling_usd=(\n                state.spend_ceiling_usd if spend_ceiling_usd is None\n                else float(spend_ceiling_usd)\n            ),\n            latency_ceiling_ms=(\n                state.latency_ceiling_ms if latency_ceiling_ms is None\n                else _validate_latency_ceiling(latency_ceiling_ms)\n            ),\n        )\n\n    def _over_budget(\n''',
)

replace_once(
    RUN,
    '''    def _needs_human(\n''',
    '''    def _over_latency(\n        self,\n        goal: str,\n        budget: int,\n        decisions: int,\n        actions: int,\n        schema: "ResultSchema | None",\n        collected: "Mapping[str, Finding]",\n        *,\n        ceiling_ms: int,\n        spent_ms: int,\n    ) -> RunOutcome:\n        """Stop before new work once measured run latency reaches its ceiling."""\n        overrun_ms = max(0, spent_ms - ceiling_ms)\n        message = (\n            f"Stopped at the latency ceiling. {spent_ms}ms of measured provider/browser "\n            f"latency has been used against a {ceiling_ms}ms ceiling"\n            + (f" ({overrun_ms}ms over from the operation already in flight). "\n               if overrun_ms else ". ")\n            + "No new operation was started after the ceiling was observed. Resume with "\n              "a higher latency ceiling to carry on from here."\n        )\n        self.trace.append(\n            Step(kind="over_latency", detail=message, url=self.page.url, ok=False),\n            captured_text=json.dumps({\n                "ceiling_ms": ceiling_ms,\n                "spent_ms": spent_ms,\n                "overrun_ms": overrun_ms,\n                "decisions": decisions,\n                "actions": actions,\n            }),\n        )\n        return self._outcome(\n            "over_latency", goal, budget, decisions, actions, message,\n            schema=schema, findings=collected,\n        )\n\n    def _needs_human(\n''',
)

replace_once(
    RUN,
    '''            spend_ceiling_usd=getattr(self, "_spend_ceiling_usd", 0.0),\n        )\n\n\ndef _remember_verification_failures(\n''',
    '''            spend_ceiling_usd=getattr(self, "_spend_ceiling_usd", 0.0),\n            latency_ceiling_ms=getattr(self, "_latency_ceiling_ms", 0),\n        )\n\n\ndef _remember_verification_failures(\n''',
)

replace_once(
    RUN,
    '''def _validate_start(goal: str, step_budget: int) -> tuple[str, int]:\n''',
    '''def _validate_latency_ceiling(value: object) -> int:\n    """Validate a caller-owned per-run latency ceiling without coercing surprises."""\n    if isinstance(value, bool) or not isinstance(value, int):\n        raise RunRefused("Latency ceiling must be a non-negative integer number of milliseconds.")\n    if value < 0:\n        raise RunRefused("Latency ceiling must be a non-negative integer number of milliseconds.")\n    return value\n\n\ndef _validate_start(goal: str, step_budget: int) -> tuple[str, int]:\n''',
)

print("S-06.02.03 source patch applied")
