"""Abstraction: hiding the *shape* of a request, not just the names in it.

Tokenisation answers "who is this about". This answers a different question that
no PII scrubber even asks: **what does the request reveal about how the business
works?**

Consider a payload with every identifier already removed::

    Third follow-up to a CTO at a 180-person Series B fintech in Berlin who
    opened twice and never replied. Our margin is 40% and we close 1 in 8.

Nothing in there is personal data. A scrubber passes it clean. And it gives away
the ICP, the buyer persona, the company-size band, the region, the sequence
design, the engagement pattern, the gross margin and the close rate — which is
most of a go-to-market strategy, handed to whichever provider happened to be
cheapest.

So there are two operations, and off_CRM needs both:

======================  ==============================  ==================
operation               removes                         protects
======================  ==============================  ==================
tokenisation            names, addresses, companies     identity
**abstraction**         the situation's specifics       strategy
======================  ==============================  ==================

**Deterministic, like everything else that enforces.** These are rules, not a
model. A model asked to "make this vaguer" would vary run to run, and a
protection that varies is not a protection. Same input, same output, forever.

**Config-driven**, like ``providers.yaml`` and ``evals.yaml``: the rules live in
``config/abstraction.yaml`` and adding one is a data edit.

**It only ever widens.** Every rule replaces something specific with something
more general. There is no rule that can make text more revealing than it was,
which is why applying it twice is safe and why an unmatched input is simply
returned unchanged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .errors import RegistryError

#: Rule kinds. Adding one means a new branch in :meth:`Rule.apply` and a new
#: ``kind`` in the config — the same shape the check registry in ``evals.py``
#: uses.
BUCKET_NUMBER = "bucket_number"
REPLACE_PATTERN = "replace_pattern"
REPLACE_TERMS = "replace_terms"

KINDS = frozenset({BUCKET_NUMBER, REPLACE_PATTERN, REPLACE_TERMS})


@dataclass(slots=True)
class Bucket:
    """One band of a numeric rule.  ``upper`` of ``None`` means "and above"."""

    upper: float | None
    label: str


@dataclass(slots=True)
class Rule:
    """One deterministic generalisation."""

    id: str
    kind: str
    pattern: re.Pattern[str] | None = None
    replacement: str = ""
    buckets: tuple[Bucket, ...] = ()
    note: str = ""

    def apply(self, text: str) -> tuple[str, int]:
        """Return the widened text and how many times this rule fired."""
        if not text:
            return text, 0
        if self.kind == REPLACE_PATTERN and self.pattern is not None:
            result, count = self.pattern.subn(self.replacement, text)
            return result, count
        if self.kind == REPLACE_TERMS and self.pattern is not None:
            result, count = self.pattern.subn(self.replacement, text)
            return result, count
        if self.kind == BUCKET_NUMBER and self.pattern is not None:
            count = 0

            def swap(match: re.Match[str]) -> str:
                nonlocal count
                raw = match.group("value")
                try:
                    value = float(raw.replace(",", "").replace("_", ""))
                except ValueError:
                    return match.group(0)
                count += 1
                return self._label_for(value)

            return self.pattern.sub(swap, text), count
        return text, 0

    def _label_for(self, value: float) -> str:
        for bucket in self.buckets:
            if bucket.upper is None or value <= bucket.upper:
                return bucket.label
        # Buckets are ordered and the last one should be open-ended; if a config
        # forgets that, widen rather than leak the number through.
        return self.buckets[-1].label if self.buckets else "an unspecified amount"


@dataclass(slots=True)
class AbstractionResult:
    """What changed, so the owner can see it rather than trust it."""

    text: str
    applied: dict[str, int] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.applied)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "changed": self.changed,
            "applied": dict(self.applied),
        }


class Abstractor:
    """Applies the rule set.  Pure: no I/O after construction, no model."""

    def __init__(self, rules: Iterable[Rule]) -> None:
        self.rules = tuple(rules)

    def abstract(self, text: str) -> AbstractionResult:
        result = str(text or "")
        applied: dict[str, int] = {}
        for rule in self.rules:
            result, count = rule.apply(result)
            if count:
                applied[rule.id] = applied.get(rule.id, 0) + count
        return AbstractionResult(text=result, applied=applied)

    def __call__(self, text: str) -> str:
        return self.abstract(text).text

    def describe(self) -> list[dict[str, str]]:
        """For the UI: what each rule does, in the owner's words."""
        return [
            {"id": rule.id, "kind": rule.kind, "note": rule.note}
            for rule in self.rules
        ]


def _compile_terms(terms: Iterable[str]) -> re.Pattern[str]:
    """Literal alternation, longest first so a longer term wins over its prefix."""
    cleaned = sorted(
        {str(term).strip() for term in terms if str(term).strip()},
        key=len,
        reverse=True,
    )
    if not cleaned:
        raise RegistryError("A replace_terms rule has no terms.")
    joined = "|".join(re.escape(term) for term in cleaned)
    return re.compile(rf"\b(?:{joined})\b", re.IGNORECASE)


def load_rules(path: Path | str) -> list[Rule]:
    """Read ``config/abstraction.yaml``.

    Fails loudly on an unknown kind or a malformed pattern: a rule that silently
    does nothing is worse than no rule, because it looks like protection.
    """
    source = Path(path)
    if not source.exists():
        raise RegistryError(
            f"No abstraction rules at {source}. Create the file, or disable "
            "abstraction for this workspace."
        )
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    rules: list[Rule] = []
    for entry in raw.get("rules", ()):
        rule_id = str(entry.get("id", "")).strip()
        kind = str(entry.get("kind", "")).strip()
        if not rule_id:
            raise RegistryError("An abstraction rule has no id.")
        if kind not in KINDS:
            raise RegistryError(
                f"Rule {rule_id!r} has unknown kind {kind!r}. Known kinds: "
                f"{', '.join(sorted(KINDS))}."
            )
        note = str(entry.get("note", "")).strip()

        if kind == REPLACE_TERMS:
            rules.append(
                Rule(
                    id=rule_id,
                    kind=kind,
                    pattern=_compile_terms(entry.get("terms", ())),
                    replacement=str(entry.get("replace", "")),
                    note=note,
                )
            )
            continue

        pattern_text = str(entry.get("pattern", ""))
        if not pattern_text:
            raise RegistryError(f"Rule {rule_id!r} has no pattern.")
        try:
            pattern = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            raise RegistryError(f"Rule {rule_id!r} has a bad pattern: {exc}") from exc

        if kind == REPLACE_PATTERN:
            rules.append(
                Rule(
                    id=rule_id,
                    kind=kind,
                    pattern=pattern,
                    replacement=str(entry.get("replace", "")),
                    note=note,
                )
            )
            continue

        # bucket_number
        if "value" not in pattern.groupindex:
            raise RegistryError(
                f"Rule {rule_id!r} is a bucket_number rule, so its pattern needs a "
                "named group (?P<value>...) marking the number to band."
            )
        buckets: list[Bucket] = []
        for band in entry.get("buckets", ()):
            upper = band.get("max")
            buckets.append(
                Bucket(
                    upper=None if upper is None else float(upper),
                    label=str(band.get("label", "")).strip(),
                )
            )
        if not buckets:
            raise RegistryError(f"Rule {rule_id!r} has no buckets.")
        if not any(bucket.upper is None for bucket in buckets):
            raise RegistryError(
                f"Rule {rule_id!r} has no open-ended bucket. Without one, a large "
                "value falls through and the number leaks. Give the last bucket "
                "max: null."
            )
        rules.append(
            Rule(id=rule_id, kind=kind, pattern=pattern, buckets=tuple(buckets), note=note)
        )
    if not rules:
        raise RegistryError(f"{source} defines no rules.")
    return rules


def default_rules_path() -> Path:
    """Packaged beside providers.yaml, so a pip install still finds it."""
    return Path(__file__).resolve().parents[2] / "config" / "abstraction.yaml"


_CACHE: dict[str, Abstractor] = {}


def abstractor_for(path: Path | str | None = None) -> Abstractor:
    """Shared, compiled instance.

    Compiling a dozen regexes on every payload build would be a silly cost for
    something that never changes within a process.
    """
    resolved = str(Path(path) if path else default_rules_path())
    if resolved not in _CACHE:
        _CACHE[resolved] = Abstractor(load_rules(resolved))
    return _CACHE[resolved]


def abstract_text(text: str, *, path: Path | str | None = None) -> str:
    """Convenience wrapper for the payload builder."""
    return abstractor_for(path)(text)
