"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .plan import PLAN_FILENAME, PlanError, PlanSnapshot, RunPlan
from .run import AgentRun, Decision, RunOutcome, RunRefused

__all__ = [
    "AgentRun",
    "Decision",
    "PLAN_FILENAME",
    "PlanError",
    "PlanSnapshot",
    "RunOutcome",
    "RunPlan",
    "RunRefused",
]
