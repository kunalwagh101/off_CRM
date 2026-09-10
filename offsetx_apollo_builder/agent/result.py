"""Caller-owned result schemas and source-bound findings for browser runs.

S-11.02.01 made the caller own the output fields. S-11.02.02 made every value
that survives that schema point back to evidence captured by off_CRM itself.
S-11.02.03 adds the next fail-closed boundary: a source-bound candidate is still
not a returned fact until deterministic verification accepts it.
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
MAX_DERIVED_INPUTS = 64
_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_FINDING_KEYS = frozenset(
    {"value", "source_step_id", "quote", "kind", "confidence", "inputs"}
)
_FINDING_KINDS = frozenset({"observed", "derived"})

VERIFY_SUPPORTED = "supported"
VERIFY_UNSUPPORTED = "unsupported"
VERIFY_TRUNCATED = "truncated"
VERIFY_DERIVED_UNVERIFIED = "derived_unverified"
_VERIFY_STATES = frozenset(
    {
        VERIFY_SUPPORTED,
        VERIFY_UNSUPPORTED,
        VERIFY_TRUNCATED,
        VERIFY_DERIVED_UNVERIFIED,
    }
)


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

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Provenance":
        """Rebuild from what `to_dict` wrote. Used when replaying a trace."""
        return cls(
            url=str(raw.get("url") or ""),
            captured_at=str(raw.get("captured_at") or ""),
            step_id=str(raw.get("step_id") or ""),
            screenshot=str(raw.get("screenshot") or ""),
            quote=str(raw.get("quote") or ""),
        )


@dataclass(frozen=True, slots=True)
class Finding:
    """One schema field whose value is bound to resolvable evidence.

    ``inputs`` names already-verified fields used by a derived finding.  A
    derived value is never allowed to cite an opaque calculation or an unsourced
    intermediate value.
    """

    field: str
    value: str
    source: Provenance
    kind: str = "observed"
    confidence: float = 0.0
    inputs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "field": self.field,
            "value": self.value,
            "kind": self.kind,
            "source": self.source.to_dict(),
            "confidence": self.confidence,
        }
        if self.inputs:
            item["inputs"] = list(self.inputs)
        return item

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Finding":
        """Rebuild from what `to_dict` wrote.  `S-11.01.03`

        A resumed run has to come back with the facts it had already gathered,
        and the only durable record of those is the trace. This is the other
        half of that round trip.

        `source` is required and not defaulted: a `Finding` without resolvable
        provenance is the one thing `S-11.02.02` exists to prevent, and quietly
        rebuilding one with an empty source would reintroduce it through the
        back door.
        """
        source = raw.get("source")
        if not isinstance(source, Mapping):
            raise ResultSchemaError(
                f"A recorded finding for {raw.get('field')!r} has no provenance "
                "and cannot be restored."
            )
        return cls(
            field=str(raw.get("field") or ""),
            value=str(raw.get("value") or ""),
            source=Provenance.from_dict(source),
            kind=str(raw.get("kind") or "observed"),
            confidence=float(raw.get("confidence") or 0.0),
            inputs=tuple(str(item) for item in (raw.get("inputs") or ())),
        )


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
    """A schema-checked record after source binding and claim verification."""

    record: dict[str, str]
    findings: dict[str, Finding]
    unfilled_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()
    unsourced_fields: tuple[str, ...] = ()
    unsupported_fields: tuple[str, ...] = ()
    truncated_fields: tuple[str, ...] = ()
    derived_unverified_fields: tuple[str, ...] = ()
    dropped_fields: tuple[str, ...] = ()
    malformed: bool = False

    @property
    def complete(self) -> bool:
        return not self.malformed and not self.unfilled_fields


SourceResolver = Callable[[str, str], Provenance | None]
FindingVerifier = Callable[[Finding, Mapping[str, Finding]], str]


@dataclass(frozen=True, slots=True)
class ResultSchema:
    """A closed, ordered set of required string fields.

    ``RunOutcome.record`` remains a simple ``field -> value`` mapping for CRM
    callers, but schema runs build that mapping only from findings that survive
    source binding and, when supplied, deterministic claim verification.
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
            "recorded only; it never makes an unsourced or unsupported field valid. "
            "For kind=derived, include inputs as a non-empty list of declared field names that "
            "were individually observed and sourced first. For kind=observed, omit inputs. "
            "If a field was not found, omit it rather than guessing or inventing a value. "
            "You may attach record fields to an act decision to save verified facts before "
            "navigating away."
        )

    def validate(self, raw: object) -> RecordValidation:
        """Legacy flat-record validator retained for compatibility tests/tools."""
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
        verify_finding: FindingVerifier | None = None,
        available_findings: Mapping[str, Finding] | None = None,
    ) -> SourcedRecordValidation:
        """Allow only declared fields whose source resolves and whose claim verifies.

        The model supplies only a trace step id and a quote. URL, timestamp and
        screenshot are resolved from off_CRM's append-only trace. Verification,
        when supplied, is deterministic host code. A missing, malformed,
        unresolvable or unsupported source never becomes a returned fact.
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
        candidates: dict[str, Finding] = {}
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

            inputs = _inputs(item.get("inputs"), kind=kind)
            if inputs is None:
                invalid.append(field)
                continue

            source = resolve_source(step_id.strip(), quote)
            if source is None:
                unsourced.append(field)
                continue

            candidates[field] = Finding(
                field=field,
                value=value,
                kind=kind,
                source=source,
                confidence=confidence,
                inputs=inputs,
            )

        record: dict[str, str] = {}
        findings: dict[str, Finding] = {}
        unsupported: list[str] = []
        truncated: list[str] = []
        derived_unverified: list[str] = []
        verified_context: dict[str, Finding] = dict(available_findings or {})

        # Observed candidates are checked first so a derived field in the same
        # model decision can depend on them without trusting output order.
        ordered = [
            *(field for field in self.fields if candidates.get(field) and candidates[field].kind == "observed"),
            *(field for field in self.fields if candidates.get(field) and candidates[field].kind == "derived"),
        ]
        for field in ordered:
            finding = candidates[field]
            state = (
                verify_finding(finding, verified_context)
                if verify_finding is not None
                else VERIFY_SUPPORTED
            )
            if state not in _VERIFY_STATES:
                state = VERIFY_UNSUPPORTED
            if state == VERIFY_SUPPORTED:
                findings[field] = finding
                record[field] = finding.value
                verified_context[field] = finding
            elif state == VERIFY_TRUNCATED:
                truncated.append(field)
            elif state == VERIFY_DERIVED_UNVERIFIED:
                derived_unverified.append(field)
            else:
                unsupported.append(field)

        unfilled = tuple(field for field in self.fields if field not in findings)
        return SourcedRecordValidation(
            record=record,
            findings=findings,
            unfilled_fields=unfilled,
            invalid_fields=tuple(field for field in self.fields if field in invalid),
            unsourced_fields=tuple(field for field in self.fields if field in unsourced),
            unsupported_fields=tuple(field for field in self.fields if field in unsupported),
            truncated_fields=tuple(field for field in self.fields if field in truncated),
            derived_unverified_fields=tuple(
                field for field in self.fields if field in derived_unverified
            ),
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


def _inputs(value: object, *, kind: str) -> tuple[str, ...] | None:
    if kind == "observed":
        if value in (None, (), []):
            return ()
        return None
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        return None
    if not value or len(value) > MAX_DERIVED_INPUTS:
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            return None
        name = item.strip()
        if not name or not _FIELD_NAME.fullmatch(name) or name in seen:
            return None
        seen.add(name)
        cleaned.append(name)
    return tuple(cleaned)


def coerce_result_schema(value: ResultSchema | Iterable[str] | None) -> ResultSchema | None:
    """Accept the public shorthand while keeping one validated internal type."""
    if value is None:
        return None
    if isinstance(value, ResultSchema):
        return value
    return ResultSchema.from_fields(value)
