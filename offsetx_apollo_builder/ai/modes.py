"""Run modes: how a task is spread across the connected providers.

The owner picks the mode per task.  All three sit on top of the same egress
broker, so the trust rules are identical whichever one runs — a mode decides
*how many* models are used and *who decides*, never *what they are allowed to
see*.

    simple        One model. The cheapest capable one that is permitted.
    compare       Every permitted model, at once. The owner reads all the
                  answers and keeps the best.
    orchestrated  A head model writes a plan, then each step is dispatched
                  through the normal router.

Safety rule specific to orchestration: **the head model must be tier A or B.**
Planning means seeing the whole shape of the job, which is the widest exposure
in the system. A restricted-tier model can still be given a step to *do* — it
just never gets to be the one deciding who does what.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .broker import EgressBroker, EgressResult, WorkspaceEgressSettings
from .errors import NoPermittedProvider, PolicyViolation
from .payload import EgressRequest
from .registry import ResolvedProvider
from .tiers import DataClass, TrustTier

#: Widest fan-out we will run at once. Beyond this the wall-clock gain is small
#: and the quota burn is real — twelve providers is twelve calls per question.
MAX_COMPARE_BRANCHES = 8

#: Tiers allowed to hold the planning role.
PLANNER_TIERS = frozenset({TrustTier.A, TrustTier.B})

#: Steps a plan may contain. A longer plan usually means the head model is
#: over-thinking, and each step costs a call.
MAX_PLAN_STEPS = 6


class RunMode(str, Enum):
    SIMPLE = "simple"
    COMPARE = "compare"
    ORCHESTRATED = "orchestrated"

    @property
    def label(self) -> str:
        return {
            RunMode.SIMPLE: "One model",
            RunMode.COMPARE: "Compare all models",
            RunMode.ORCHESTRATED: "Let a lead model plan it",
        }[self]

    @property
    def description(self) -> str:
        return {
            RunMode.SIMPLE: (
                "Picks the cheapest model that is allowed and good at this. "
                "Fastest and cheapest. Use this for everyday work."
            ),
            RunMode.COMPARE: (
                "Asks every allowed model the same question at the same time, "
                "then shows you all the answers side by side so you pick the "
                "best. Uses one call per model."
            ),
            RunMode.ORCHESTRATED: (
                "A lead model breaks the job into steps and sends each step to "
                "whichever model suits it. Best for big jobs. Costs one extra "
                "call for the planning."
            ),
        }[self]


@dataclass(slots=True)
class Branch:
    """One model's answer in compare mode."""

    provider_id: str
    provider_name: str
    model_id: str
    jurisdiction: str
    tier: str
    policy: str
    flag: str = ""
    text: str = ""
    error: str = ""
    duration_ms: int = 0
    payload_fields: list[str] = field(default_factory=list)
    log_id: str = ""
    estimated_cost_usd: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "jurisdiction": self.jurisdiction,
            "tier": self.tier,
            "policy": self.policy,
            "flag": self.flag,
            "text": self.text,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "payload_fields": self.payload_fields,
            "log_id": self.log_id,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "ok": self.ok,
        }


@dataclass(slots=True)
class PlanStep:
    """One step of an orchestrated run."""

    index: int
    title: str
    instructions: str
    data_class: DataClass = DataClass.PUBLIC
    tags: tuple[str, ...] = ()
    assigned_provider_id: str = ""
    assigned_provider_name: str = ""
    text: str = ""
    error: str = ""
    duration_ms: int = 0
    log_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "instructions": self.instructions,
            "data_class": self.data_class.value,
            "tags": list(self.tags),
            "assigned_provider_id": self.assigned_provider_id,
            "assigned_provider_name": self.assigned_provider_name,
            "text": self.text,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "log_id": self.log_id,
            "ok": not self.error and bool(self.text),
        }


@dataclass(slots=True)
class RunResult:
    mode: str
    data_class: str
    branches: list[Branch] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)
    planner_provider_id: str = ""
    planner_provider_name: str = ""
    planner_tier: str = ""
    excluded: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def best_text(self) -> str:
        """The single answer a caller should use when it wants just one."""
        if self.steps:
            done = [step for step in self.steps if step.text]
            return done[-1].text if done else ""
        ok = [branch for branch in self.branches if branch.ok]
        return ok[0].text if ok else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "data_class": self.data_class,
            "branches": [item.to_dict() for item in self.branches],
            "steps": [item.to_dict() for item in self.steps],
            "planner_provider_id": self.planner_provider_id,
            "planner_provider_name": self.planner_provider_name,
            "planner_tier": self.planner_tier,
            "excluded": self.excluded,
            "total_duration_ms": self.total_duration_ms,
            "notes": self.notes,
            "best_text": self.best_text,
        }


PLANNER_SYSTEM_PROMPT = """You break a job into a small number of steps.

You are planning only. You do not do the work and you do not have access to any
database, mailbox or file. You receive a description of the job and a list of
available worker models, and you return a plan.

Return ONLY a JSON object of this exact shape:

{"steps": [
  {"title": "short name",
   "instructions": "what the worker must produce",
   "needs": "public" | "person_public" | "campaign",
   "tags": ["writing"|"reasoning"|"code"|"architecture"|"planning"|"classification"|"bulk"]}
]}

Rules:
- At most 6 steps. Fewer is better. If one step is enough, return one step.
- "needs" is the most sensitive kind of information that step requires.
  Use "public" whenever the step does not involve a specific person.
- Each step's instructions must stand alone. A worker sees only its own step.
- Never ask for an email address, a mailbox, or database contents. You will not
  get them and the step will be refused."""


class ModeRunner:
    """Runs a task in whichever mode the owner chose.

    Every path goes through :class:`EgressBroker`, so nothing here can widen
    what a provider receives.
    """

    def __init__(self, broker: EgressBroker) -> None:
        self.broker = broker

    # ── mode: simple ────────────────────────────────────────────────────────

    def run_simple(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        system_prompt: str,
        provider_id: str = "",
    ) -> RunResult:
        started = time.monotonic()
        result = self.broker.call(
            request, settings, system_prompt=system_prompt, provider_id=provider_id
        )
        return RunResult(
            mode=RunMode.SIMPLE.value,
            data_class=request.data_class.value,
            branches=[self._branch_from(result)],
            excluded=result.rejected,
            total_duration_ms=int((time.monotonic() - started) * 1000),
        )

    # ── mode: compare ───────────────────────────────────────────────────────

    def run_compare(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        system_prompt: str,
        include_lower_tiers: bool = True,
        max_branches: int = MAX_COMPARE_BRANCHES,
    ) -> RunResult:
        """Ask every permitted model the same question, at the same time.

        Unlike the failover chain, compare mode may reach across tiers — but
        each model still runs under *its own* policy. A tier C model in the line
        up receives a smaller payload than a tier A one, automatically. That is
        the point: you get its answer without giving it more than it should have.
        """
        started = time.monotonic()
        candidates, excluded = self._all_permitted(
            request, settings, include_lower_tiers=include_lower_tiers
        )
        if not candidates:
            raise NoPermittedProvider(
                "No connected model may handle this task. Open Connectors to add one, "
                "or switch the task to a public question.",
                considered=excluded,
            )

        candidates = candidates[:max_branches]
        notes: list[str] = []
        tiers_used = {candidate.tier for candidate in candidates}
        if len(tiers_used) > 1:
            notes.append(
                "Models at different trust levels answered. Each one received only "
                "what its own level allows, so the answers are not based on the same "
                "amount of detail."
            )

        branches: list[Branch] = []
        with ThreadPoolExecutor(
            max_workers=len(candidates), thread_name_prefix="offsetx-compare"
        ) as executor:
            futures = {
                executor.submit(
                    self._call_one, request, settings, system_prompt, candidate.id
                ): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    branches.append(future.result())
                except Exception as exc:  # noqa: BLE001 - one failure is not fatal
                    branches.append(
                        Branch(
                            provider_id=candidate.id,
                            provider_name=candidate.name,
                            model_id=candidate.model_id,
                            jurisdiction=candidate.entry.jurisdiction,
                            tier=candidate.tier.value,
                            policy=candidate.policy.value,
                            flag=candidate.entry.flag,
                            error=str(exc)[:400],
                        )
                    )

        # Trusted first, then fastest — the order the owner should read them in.
        branches.sort(key=lambda item: (item.tier, -0 if item.ok else 1, item.duration_ms))
        return RunResult(
            mode=RunMode.COMPARE.value,
            data_class=request.data_class.value,
            branches=branches,
            excluded=excluded,
            total_duration_ms=int((time.monotonic() - started) * 1000),
            notes=notes,
        )

    # ── mode: orchestrated ──────────────────────────────────────────────────

    def run_orchestrated(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        system_prompt: str,
        planner_provider_id: str = "",
    ) -> RunResult:
        """A head model writes a plan; each step then runs through the router.

        The head model is chosen from tier A or B only. It receives the job
        description and the *names and strengths* of the available workers — not
        the data, and not the other steps' outputs.
        """
        started = time.monotonic()
        planner = self._choose_planner(settings, planner_provider_id)
        workers, excluded = self._all_permitted(request, settings, include_lower_tiers=True)

        plan_request = EgressRequest(
            task_type="orchestrator_plan",
            # The plan itself describes work; it carries no person and no
            # template, so it is public by construction.
            data_class=DataClass.PUBLIC,
            instructions=self._plan_brief(request, workers),
            task_tags=("planning", "reasoning", "architecture"),
        )
        plan_result = self.broker.call(
            plan_request,
            settings,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            provider_id=planner.id,
        )
        steps = self._parse_plan(plan_result.text, request)

        notes: list[str] = []
        if not steps:
            notes.append(
                "The lead model did not return a usable plan, so the job ran as a "
                "single step instead."
            )
            steps = [
                PlanStep(
                    index=0,
                    title="Do the job",
                    instructions=request.instructions or "Complete the task.",
                    data_class=request.data_class,
                    tags=request.task_tags,
                )
            ]

        for step in steps:
            step_request = EgressRequest(
                task_type=f"orchestrated_step:{step.title[:40]}",
                data_class=step.data_class,
                instructions=step.instructions,
                person=request.person if step.data_class is not DataClass.PUBLIC else None,
                positioning_line=request.positioning_line,
                template_text=(
                    request.template_text
                    if step.data_class is DataClass.CAMPAIGN
                    else ""
                ),
                public_text=request.public_text,
                task_tags=step.tags,
            )
            try:
                outcome = self.broker.call(
                    step_request, settings, system_prompt=system_prompt
                )
                step.text = outcome.text
                step.assigned_provider_id = outcome.provider_id
                step.assigned_provider_name = outcome.provider_name
                step.duration_ms = outcome.duration_ms
                step.log_id = outcome.log_id
            except (NoPermittedProvider, PolicyViolation) as exc:
                # A step the plan asked for but the rules forbid does not sink
                # the run — it is reported and the rest continues.
                step.error = str(exc)[:400]
                notes.append(f'Step "{step.title}" was refused: {step.error}')

        return RunResult(
            mode=RunMode.ORCHESTRATED.value,
            data_class=request.data_class.value,
            steps=steps,
            planner_provider_id=planner.id,
            planner_provider_name=planner.name,
            planner_tier=planner.tier.value,
            excluded=excluded,
            total_duration_ms=int((time.monotonic() - started) * 1000),
            notes=notes,
        )

    # ── internals ───────────────────────────────────────────────────────────

    def _choose_planner(
        self, settings: WorkspaceEgressSettings, requested_id: str
    ) -> ResolvedProvider:
        """Pick the head model. Tier A or B only — this is not negotiable.

        Deciding who does what means seeing the whole job, so the planning role
        is held to the same standard as CRM data even though the plan brief
        itself is public.
        """
        eligible: list[ResolvedProvider] = []
        for provider_id in settings.enabled_provider_ids:
            try:
                resolved = self.broker.registry.resolve(
                    provider_id, override=settings.overrides.get(provider_id)
                )
            except Exception:  # noqa: BLE001 - unlisted providers simply skip
                continue
            if resolved.tier in PLANNER_TIERS:
                eligible.append(resolved)

        if requested_id:
            chosen = next((item for item in eligible if item.id == requested_id), None)
            if chosen is None:
                raise PolicyViolation(
                    "That model cannot lead a plan. Planning means seeing the whole "
                    "job, so only models at Highest or Default trust can do it. The "
                    "model you picked can still be given individual steps to work on.",
                    provider_id=requested_id,
                )
            return chosen

        if not eligible:
            raise NoPermittedProvider(
                "No model connected here can lead a plan. Planning needs a model at "
                "Highest or Default trust — for example Mistral, Claude, GPT or "
                "NVIDIA. Connect one in Connectors, or use 'One model' mode instead."
            )
        # Prefer the most trusted, then the strongest planner, then the cheapest.
        eligible.sort(
            key=lambda item: (
                -item.tier.rank,
                0 if {"planning", "reasoning", "architecture"} & set(
                    (item.model.good_at if item.model else ())
                ) else 1,
                item.cost,
            )
        )
        return eligible[0]

    def _all_permitted(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        *,
        include_lower_tiers: bool,
    ) -> tuple[list[ResolvedProvider], list[dict[str, Any]]]:
        """Everything allowed to hold this data class.

        ``broker.plan`` narrows to a single tier because failover must never
        demote. Compare mode wants the full permitted set, so it asks the
        registry directly — each model still runs under its own policy.
        """
        if not settings.enabled_provider_ids:
            return [], [
                {
                    "provider_id": "",
                    "reason": "none_connected",
                    "detail": "No AI provider is connected for this workspace.",
                }
            ]
        if request.data_class is DataClass.MAILBOX and not settings.mailbox_unlocked:
            raise PolicyViolation(
                "Mailbox content cannot be sent to any AI provider.",
                data_class=request.data_class.value,
            )
        permitted, rejected = self.broker.registry.candidates_for(
            request.data_class,
            enabled_ids=settings.enabled_provider_ids,
            overrides=settings.overrides,
            mailbox_unlocked=settings.mailbox_unlocked,
            task_tags=request.task_tags,
        )
        if not include_lower_tiers and permitted:
            best = max(item.tier.rank for item in permitted)
            permitted = [item for item in permitted if item.tier.rank == best]
        return permitted, rejected

    def _call_one(
        self,
        request: EgressRequest,
        settings: WorkspaceEgressSettings,
        system_prompt: str,
        provider_id: str,
    ) -> Branch:
        result = self.broker.call(
            request, settings, system_prompt=system_prompt, provider_id=provider_id
        )
        return self._branch_from(result)

    def _branch_from(self, result: EgressResult) -> Branch:
        entry = self.broker.registry.get(result.provider_id)
        model = entry.model(result.model_id) if entry else None
        # Rough token estimate: ~4 characters per token is close enough for a
        # cost hint, and we are not billing anyone from it.
        tokens = max(1, len(result.text) // 4)
        cost = (model.cost_per_1m_output_usd * tokens / 1_000_000) if model else 0.0
        return Branch(
            provider_id=result.provider_id,
            provider_name=result.provider_name,
            model_id=result.model_id,
            jurisdiction=entry.jurisdiction if entry else "",
            tier=result.tier,
            policy=result.policy,
            flag=entry.flag if entry else "",
            text=result.text,
            duration_ms=result.duration_ms,
            payload_fields=result.payload_fields,
            log_id=result.log_id,
            estimated_cost_usd=cost,
        )

    @staticmethod
    def _plan_brief(request: EgressRequest, workers: Iterable[ResolvedProvider]) -> str:
        """What the head model is told.

        Worker names and strengths, plus the job description. No person, no
        template, no addresses — the plan is about shape, not content.
        """
        lines = [
            f"Job: {request.instructions or request.task_type}",
            "",
            "Available worker models:",
        ]
        for worker in workers:
            model = worker.model
            strengths = ", ".join(model.good_at) if model and model.good_at else "general"
            lines.append(f"- {worker.name}: good at {strengths}")
        lines.append("")
        lines.append("Return the JSON plan described in your instructions.")
        return "\n".join(lines)

    @staticmethod
    def _parse_plan(text: str, request: EgressRequest) -> list[PlanStep]:
        """Read the head model's JSON plan, defensively.

        Model output is untrusted input. A plan that asks for a data class the
        request never offered is clamped down, not honoured — a planner cannot
        widen its own reach by asking nicely.
        """
        payload: Any = None
        candidate = str(text or "").strip()
        if candidate.startswith("```"):
            candidate = "\n".join(
                line for line in candidate.splitlines() if not line.startswith("```")
            )
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start >= 0 and end > start:
                try:
                    payload = json.loads(candidate[start : end + 1])
                except json.JSONDecodeError:
                    return []
        if not isinstance(payload, dict):
            return []
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            return []

        allowed = {DataClass.PUBLIC, DataClass.PERSON_PUBLIC, DataClass.CAMPAIGN}
        ceiling = request.data_class
        steps: list[PlanStep] = []
        for index, raw in enumerate(raw_steps[:MAX_PLAN_STEPS]):
            if not isinstance(raw, dict):
                continue
            instructions = str(raw.get("instructions", "")).strip()
            if not instructions:
                continue
            wanted = str(raw.get("needs", "public")).strip().lower()
            data_class = DataClass.PUBLIC
            if wanted in {item.value for item in DataClass}:
                requested = DataClass(wanted)
                if requested in allowed:
                    data_class = requested
            # Never above what the caller itself asked for.
            if ceiling is DataClass.PUBLIC:
                data_class = DataClass.PUBLIC
            elif ceiling is DataClass.PERSON_PUBLIC and data_class is DataClass.CAMPAIGN:
                data_class = DataClass.PERSON_PUBLIC

            tags = tuple(
                str(tag).strip().lower()
                for tag in (raw.get("tags") or ())
                if str(tag).strip()
            )[:4]
            steps.append(
                PlanStep(
                    index=index,
                    title=str(raw.get("title", f"Step {index + 1}")).strip()[:80]
                    or f"Step {index + 1}",
                    instructions=instructions[:4000],
                    data_class=data_class,
                    tags=tags,
                )
            )
        return steps
