"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .result import (
    Finding,
    Provenance,
    RecordValidation,
    ResultSchema,
    ResultSchemaError,
    SourcedRecordValidation,
)
from .run import AgentRun, Decision, ResumeState, RunOutcome, RunRefused, replay
from .watch import Progress, console

__all__ = [
    "AgentRun",
    "console",
    "Decision",
    "Finding",
    "Progress",
    "Provenance",
    "RecordValidation",
    "ResultSchema",
    "ResultSchemaError",
    "RunOutcome",
    "RunRefused",
    "ResumeState",
    "replay",
    "SourcedRecordValidation",
]
