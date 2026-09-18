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
from .routines import AgentRunRoutineExecutor, Routine, RoutineError, RoutineService, RoutineStore, Trigger
from .watch import Progress, console

__all__ = [
    "AgentRun",
    "AgentRunRoutineExecutor",
    "console",
    "Decision",
    "Finding",
    "Progress",
    "Provenance",
    "RecordValidation",
    "ResultSchema",
    "ResultSchemaError",
    "Routine",
    "RoutineError",
    "RoutineService",
    "RoutineStore",
    "RunOutcome",
    "RunRefused",
    "ResumeState",
    "replay",
    "SourcedRecordValidation",
    "Trigger",
]
