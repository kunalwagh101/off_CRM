"""Caller-owned result schemas for autonomous browser runs.

S-11.02.01 changes one boundary and deliberately stops there: the owner names
which fields a run must return, the model fills those fields, and off_CRM
validates the result in plain code.  The model never gets to widen its own
output contract.

This module does *not* attach provenance yet.  S-11.02.02 owns that next step.
Keeping schema validation independent means provenance can wrap a validated
field without re-opening which field names are allowed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

MAX_SCHEMA_FIELDS = 64
MAX_FIELD_NAME_CHARS = 100
MAX_FIELD_VALUE_CHARS = 20_000
_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


class ResultSchemaError(ValueError):
    """A caller supplied a result schema that cannot be enforced safely."""


@dataclass(frozen=True, slots=True)
class RecordValidation:
    """The deterministic result of applying one schema to a model record."""

    record: dict[str, str]
    missing_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    malformed: bool = False

    @property
    def unfilled_fields(self) -> tuple[str, ...]:
        """Required fields the run did not produce as usable string values."""
        unfilled = set(self.missing_fields) | set(self.invalid_fields)
        return tuple(field for field in self.record_schema_order if field in unfilled)

    @property
    def record_schema_order(self) -> tuple[str, ...]:
        """Stable order for diagnostics without storing a second schema object.

        Valid fields keep insertion order, and missing/invalid tuples were built
        in schema order.  Joining them this way is deterministic for logs and
        API responses.
        """
        ordered: list[str] = list(self.record)
        for field in (*self.missing_fields, *self.invalid_fields):
            if field not in ordered:
                ordered.append(field)
        return tuple(ordered)

    @property
    def complete(self) -> bool:
        return not self.malformed and not self.missing_fields and not self.invalid_fields


@dataclass(frozen=True, slots=True)
class ResultSchema:
    """A closed, ordered set of required string fields.

    The final E-11 ``Finding.value`` contract is a string, so this first story
    does not invent a second type system.  A field the model cannot fill is
    omitted and makes the run incomplete; a non-string value is not silently
    coerced because coercion can change the fact being recorded.
    """

    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        raw = tuple(self.fields)
        if not raw:
            raise ResultSchemaError("A result schema needs at least one field.")
        if len(raw) > MAX_SCHEMA_FIELDS:
            raise ResultSchemaError(
                f"A result schema may declare at most {MAX_SCHEMA_FIELDS} fields."
            )

        cleaned: list[str] = []
        seen: set[str] = set()
        for value in raw:
            if not isinstance(value, str):
                raise ResultSchemaError("Every result field name must be a string.")
            name = value.strip()
            if not name:
                raise ResultSchemaError("Result field names cannot be empty.")
            if len(name) > MAX_FIELD_NAME_CHARS:
                raise ResultSchemaError(
                    f"Result field {name[:40]!r} is longer than {MAX_FIELD_NAME_CHARS} characters."
                )
            if not _FIELD_NAME.fullmatch(name):
                raise ResultSchemaError(
                    f"Result field {name!r} is not a stable machine field name. "
                    "Use letters, digits, underscore, dot or hyphen."
                )
            if name in seen:
                raise ResultSchemaError(f"Result field {name!r} is declared more than once.")
            seen.add(name)
            cleaned.append(name)

        object.__setattr__(self, "fields", tuple(cleaned))

    @classmethod
    def from_fields(cls, fields: Iterable[str]) -> "ResultSchema":
        if isinstance(fields, (str, bytes)):
            raise ResultSchemaError("Pass result fields as a collection, not one string.")
        return cls(tuple(fields))

    def prompt_contract(self) -> str:
        """Trusted text inserted into the model request beside the owner goal."""
        names = ", ".join(self.fields)
        return (
            "When the goal is complete, return a JSON object with state=done and a record object. "
            f"The record may contain ONLY these required fields: {names}. "
            "Every value must be a JSON string. If a field was not found, omit it rather than "
            "guessing or inventing a value."
        )

    def validate(self, raw: object) -> RecordValidation:
        """Apply the caller's allowlist and report every mismatch.

        Extra fields are dropped. Missing, empty, over-sized or non-string
        values never become facts.  No model call is involved in this decision.
        """
        if not isinstance(raw, Mapping):
            return RecordValidation(
                record={},
                missing_fields=self.fields,
                malformed=raw is not None,
            )

        allowed = set(self.fields)
        dropped = tuple(sorted(str(key) for key in raw if key not in allowed))
        record: dict[str, str] = {}
        missing: list[str] = []
        invalid: list[str] = []

        for field in self.fields:
            if field not in raw:
                missing.append(field)
                continue
            value: Any = raw[field]
            if not isinstance(value, str) or not value.strip():
                invalid.append(field)
                continue
            if len(value) > MAX_FIELD_VALUE_CHARS:
                invalid.append(field)
                continue
            # Preserve the value byte-for-byte. S-11.02.03 will normalise only
            # for comparison; the returned value itself remains what the model
            # transcribed so it can be audited later.
            record[field] = value

        return RecordValidation(
            record=record,
            missing_fields=tuple(missing),
            invalid_fields=tuple(invalid),
            dropped_fields=dropped,
        )


def coerce_result_schema(value: ResultSchema | Iterable[str] | None) -> ResultSchema | None:
    """Accept the public shorthand while keeping one validated internal type."""
    if value is None:
        return None
    if isinstance(value, ResultSchema):
        return value
    return ResultSchema.from_fields(value)
