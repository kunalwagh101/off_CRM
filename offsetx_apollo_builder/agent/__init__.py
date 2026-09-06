"""Bounded autonomous work loops built on off_CRM's existing safety boundaries."""

from .result import (
    Finding,
    Provenance,
    RecordValidation,
    ResultSchema,
    ResultSchemaError,
    SourcedRecordValidation,
)
from .run import AgentRun, Decision, RunOutcome, RunRefused

__all__ = [
    "AgentRun",
    "Decision",
    "Finding",
    "Provenance",
    "RecordValidation",
    "ResultSchema",
    "ResultSchemaError",
    "RunOutcome",
    "RunRefused",
    "SourcedRecordValidation",
]
