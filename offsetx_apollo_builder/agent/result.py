"""Caller-owned result schemas and source-bound findings for browser runs.

S-11.02.01 made the caller own the output fields. S-11.02.02 makes every value
that survives that schema point back to evidence captured by off_CRM itself.
The model may name a trace step and quote text; it may not invent the URL,
timestamp or screenshot metadata. Those are resolved from the append-only trace
in deterministic code.

Claim verification is intentionally still separate. S-11.02.03 will check that
an observed value is actually present in the captured text. This module only
answers the prior question: *where did the model say this came from, and does
that source really exist in this run?*
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

MAX_SCHEMA_FIELDS = 64
MAX_FIELD_NAME_CHARS = 100
MAX_FIELD_VALUE_CHARS = 20_000
MAX_QUOTE_CHARS = 4_000
_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_FINDING_KEYS = frozenset({"value", "source_step_id", "quote", "kind", "confidence"})
_FINDING_KINDS = frozenset({"observed", "derived"})


class ResultSchemaError(ValueError):
    """A caller supplied a result schema that cannot be enforced safely."""


@dataclass(frozen=True, slots=True)
class Provenance:
    """Evidence metadata resolved from one immutable trace step."""

    url: str
    captured_at: str
    step_id: str
    screenshot: str
    quote: str

    def to_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "captured_at": self.captured_at,
            "step_id": self.step_id,
            "screenshot": self.screenshot,
            "quote": self.quote,
        }


@dataclass(frozen=True, slots=True)
class Finding:
    """One schema field whose value is bound to resolvable evidence."""

    field: str
    value: str
    source: Provenance
    kind: str = "observed"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "value": self.value,
            "kind": self.kind,
            "source": self.source.to_dict(),
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class RecordValidation:
    """The deterministic result of applying one schema to a legacy flat record."""

    record: dict[str, str]
    unfilled_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    malformed: bool = False

    @property
    def complete(self) -> bool:
        return not self.malformed and not self.unfilled_fields


@dataclass(frozen=True, slots=True)
class SourcedRecordValidation:
    """A schema-checked record after every surviving field has a real source."""

    record: dict[str, str]
    findings: dict[str, Finding]
    unfilled_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()
    unsourced_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    malformed: bool = False

    @property
    def complete(self) -> bool:
        return not self.malformed and not self.unfilled_fields


SourceResolver = Callable[[str, str], Provenance | None]


@dataclass(frozen=True, slots=True)
class ResultSchema:
    """A closed, ordered set of required string fields.

    ``RunOutcome.record`` remains a simple ``field -> value`` mapping for CRM
    callers, but schema runs now build that mapping only from source-bound
    :class:`Finding` objects. The compatibility view is therefore convenient,
    not a second unsourced truth store.
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
            "When you have a requested fact, put it in record under its declared field name. "
            f"The record may contain ONLY these required fields: {names}. "
            "Each field value must be an object with value, source_step_id, quote, kind and "
            "confidence. source_step_id must be one of the SOURCE EVIDENCE step ids off_CRM "
            "showed you after a read. kind is observed or derived. confidence is 0 to 1 and is "
            "recorded only; it never makes an unsourced field valid. If a field was not found, "
            "omit it rather than guessing or inventing a value. You may attach record fields to "
            "an act decision to save sourced facts before navigating away."
        )

    def validate(self, raw: object) -> RecordValidation:
        """Legacy flat-record validator retained for compatibility tests/tools.

        Production schema runs use :meth:`validate_sourced`. Keeping this method
        avoids turning a source-binding story into an unrelated API removal.
        """
        if not isinstance(raw, Mapping):
            return RecordValidation(
                record={},
                unfilled_fields=self.fields,
                malformed=raw is not None,
            )

        allowed = set(self.fields)
        dropped = tuple(sorted(str(key) for key in raw if key not in allowed))
        record: dict[str, str] = {}
        unfilled: list[str] = []
        invalid: list[str] = []

        for field in self.fields:
            if field not in raw:
                unfilled.append(field)
                continue
            value: Any = raw[field]
            if not _usable_value(value):
                invalid.append(field)
                unfilled.append(field)
                continue
            record[field] = value

        return RecordValidation(
            record=record,
            unfilled_fields=tuple(unfilled),
            invalid_fields=tuple(invalid),
            dropped_fields=dropped,
        )

    def validate_sourced(
        self,
        raw: object,
        *,
        resolve_source: SourceResolver,
    ) -> SourcedRecordValidation:
        """Allow only declared fields whose source resolves inside this run.

        The model supplies only a trace step id and a quote. URL, timestamp and
        screenshot are resolved by ``resolve_source`` from off_CRM's append-only
        trace. A missing, malformed or unresolvable source never becomes a fact.
        """
        if raw is None:
            return SourcedRecordValidation(record={}, findings={})
        if not isinstance(raw, Mapping):
            return SourcedRecordValidation(
                record={},
                findings={},
                unfilled_fields=self.fields,
                malformed=True,
            )

        allowed = set(self.fields)
        dropped = tuple(sorted(str(key) for key in raw if key not in allowed))
        record: dict[str, str] = {}
        findings: dict[str, Finding] = {}
        invalid: list[str] = []
        unsourced: list[str] = []

        for field in self.fields:
            if field not in raw:
                continue
            item = raw[field]
            if not isinstance(item, Mapping):
                invalid.append(field)
                continue
            if set(item) - _FINDING_KEYS:
                invalid.append(field)
                continue

            value = item.get("value")
            step_id = item.get("source_step_id")
            quote = item.get("quote")
            kind = str(item.get("kind") or "observed").strip().lower()
            confidence = _confidence(item.get("confidence", 0.0))

            if not _usable_value(value):
                invalid.append(field)
                continue
            if not isinstance(step_id, str) or not step_id.strip():
                unsourced.append(field)
                continue
            if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE_CHARS:
                invalid.append(field)
                continue
            if kind not in _FINDING_KINDS or confidence is None:
                invalid.append(field)
                continue

            source = resolve_source(step_id.strip(), quote)
            if source is None:
                unsourced.append(field)
                continue

            finding = Finding(
                field=field,
                value=value,
                kind=kind,
                source=source,
                confidence=confidence,
            )
            findings[field] = finding
            record[field] = value

        unfilled = tuple(field for field in self.fields if field not in findings)
        return SourcedRecordValidation(
            record=record,
            findings=findings,
            unfilled_fields=unfilled,
            invalid_fields=tuple(field for field in self.fields if field in invalid),
            unsourced_fields=tuple(field for field in self.fields if field in unsourced),
            dropped_fields=dropped,
        )


def _usable_value(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= MAX_FIELD_VALUE_CHARS


def _confidence(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 1:
        return None
    return number


def coerce_result_schema(value: ResultSchema | Iterable[str] | None) -> ResultSchema | None:
    """Accept the public shorthand while keeping one validated internal type."""
    if value is None:
        return None
    if isinstance(value, ResultSchema):
        return value
    return ResultSchema.from_fields(value)
