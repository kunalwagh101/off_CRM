"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .run import AgentRun, Decision, RunOutcome, RunRefused

__all__ = ["AgentRun", "Decision", "RunOutcome", "RunRefused"]
