"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .companions import Companion, CompanionError, CompanionStore, MemorySnapshot
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
    "Companion",
    "CompanionError",
    "CompanionStore",
    "MemorySnapshot",
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
