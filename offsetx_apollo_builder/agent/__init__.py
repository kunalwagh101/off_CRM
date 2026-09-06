"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .result import RecordValidation, ResultSchema, ResultSchemaError
from .run import AgentRun, Decision, RunOutcome, RunRefused

__all__ = [
    "AgentRun",
    "Decision",
    "RecordValidation",
    "ResultSchema",
    "ResultSchemaError",
    "RunOutcome",
    "RunRefused",
]
