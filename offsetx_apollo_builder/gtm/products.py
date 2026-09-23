"""The product, described once.

Every generator in off_CRM used to take its own loose string: the email writer a
positioning line from Settings, the post pipeline an angle typed per call, the
director a house style. Three channels, three slightly different stories. This
is the one record they all read instead.

**Pure on purpose.** No database, no model, no network. Validation is a function
of its input so it can be tested exactly, and so anything that needs to check a
product — the store, the API, the strategy brain — runs the same rules.

**An address is refused at the door.** Everything here may be sent to a model as
campaign material. The pre-flight scanner would block any call carrying an
address, and the owner would see that refusal three screens later with no idea
why. Refusing it here, with the reason, is the same outcome sooner and readable.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

#: field -> (minimum characters, maximum characters, required)
TEXT_FIELDS: dict[str, tuple[int, int, bool]] = {
    "name": (1, 80, True),
    "one_liner": (10, 200, True),
    "audience": (10, 600, True),
    "problem": (10, 600, True),
    "outcome": (0, 600, False),
    "offer": (3, 200, True),
    "voice": (0, 300, False),
    "website": (0, 300, False),
}

#: field -> (maximum items, minimum characters per item, maximum per item)
LIST_FIELDS: dict[str, tuple[int, int, int]] = {
    "proof": (8, 3, 200),
    "differentiators": (6, 3, 200),
    "forbidden_claims": (20, 2, 120),
}

FIELDS: tuple[str, ...] = tuple(TEXT_FIELDS) + tuple(LIST_FIELDS)

#: How a field is named in a sentence the owner reads.
LABELS: dict[str, str] = {
    "name": "name",
    "one_liner": "one-liner",
    "audience": "audience",
    "problem": "problem",
    "outcome": "outcome",
    "offer": "offer",
    "voice": "voice",
    "website": "website",
    "proof": "proof",
    "differentiators": "differentiators",
    "forbidden_claims": "forbidden claims",
}

#: The scanner's own address pattern (`ai/scanner.py`), repeated rather than
#: imported because importing anything from `ai/` imports the broker.
#: `test_address_pattern_matches_the_scanners` fails if the two ever differ, so
#: what the form refuses is exactly what the scanner would block.
ADDRESS = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


class ProductInvalid(ValueError):
    """A product that cannot be saved, with the field that stopped it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _collapse(value: object) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def _label(field: str) -> str:
    return LABELS.get(field, field)


def _refuse_address(field: str, text: str) -> None:
    if ADDRESS.search(text):
        raise ProductInvalid(
            field,
            f"The {_label(field)} contains an email address. Anything in the product "
            "may be sent to a model, and an address would be blocked on every call — "
            "put contact addresses in Settings instead.",
        )


def _text(field: str, raw: object) -> str:
    if raw is not None and not isinstance(raw, (str, int, float)):
        raise ProductInvalid(field, f"The {_label(field)} must be text.")
    minimum, maximum, required = TEXT_FIELDS[field]
    value = _collapse(raw)
    if required and not value:
        raise ProductInvalid(field, f"The {_label(field)} is required.")
    if value and len(value) < minimum:
        raise ProductInvalid(
            field, f"The {_label(field)} needs at least {minimum} characters to be useful."
        )
    if len(value) > maximum:
        raise ProductInvalid(
            field,
            f"The {_label(field)} is {len(value)} characters; the limit is {maximum}.",
        )
    _refuse_address(field, value)
    if field == "website" and value:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or " " in value:
            raise ProductInvalid(
                field,
                "The website must be a full address starting with http:// or https://.",
            )
    return value


def _list(field: str, raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise ProductInvalid(field, f"The {_label(field)} must be a list of short lines.")
    most, minimum, maximum = LIST_FIELDS[field]
    kept: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if item is not None and not isinstance(item, (str, int, float)):
            raise ProductInvalid(field, f"Each line of the {_label(field)} must be text.")
        value = _collapse(item)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        if len(value) < minimum:
            raise ProductInvalid(
                field,
                f"A line of the {_label(field)} needs at least {minimum} characters: "
                f"{value!r}.",
            )
        if len(value) > maximum:
            raise ProductInvalid(
                field,
                f"A line of the {_label(field)} is {len(value)} characters; the limit "
                f"is {maximum}.",
            )
        _refuse_address(field, value)
        seen.add(key)
        kept.append(value)
    if len(kept) > most:
        raise ProductInvalid(
            field, f"The {_label(field)} has {len(kept)} lines; the limit is {most}."
        )
    return kept


def validate_product(values: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
    """Clean and check a product, or refuse it with the field named.

    ``partial`` is an edit: only the fields present are checked and returned, so
    an edit to the voice does not re-demand the whole product. A field nobody
    declared is refused rather than dropped — a silently ignored ``pricing``
    field is the owner believing something was saved that was not.
    """
    if not isinstance(values, Mapping):
        raise ProductInvalid("product", "A product must be an object of named fields.")
    for key in values:
        if key not in FIELDS:
            raise ProductInvalid(
                str(key),
                f"{key!r} is not a product field. Known fields: {', '.join(FIELDS)}.",
            )
    cleaned: dict[str, Any] = {}
    for field in TEXT_FIELDS:
        if partial and field not in values:
            continue
        cleaned[field] = _text(field, values.get(field))
    for field in LIST_FIELDS:
        if partial and field not in values:
            continue
        cleaned[field] = _list(field, values.get(field))
    return cleaned


def _phrase_pattern(claim: str) -> re.Pattern[str]:
    """A claim as a whole phrase, however it is spaced.

    Anchored on **alphanumeric lookarounds, not ``\\b``**. A word boundary never
    matches after ``%``, so ``\\b100% accuracy\\b`` would miss the very sentence
    it exists to catch — the same class of bug that let a margin leak through
    ``ai/abstraction.py``. Lookarounds anchor both ends whatever the phrase
    starts or ends with.
    """
    words = [re.escape(part) for part in _collapse(claim).split(" ") if part]
    body = r"\s+".join(words)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def find_forbidden(text: str, claims: Sequence[str]) -> list[str]:
    """The owner's forbidden claims that appear in ``text``, as the owner wrote them."""
    haystack = str(text or "")
    if not haystack.strip():
        return []
    found: list[str] = []
    for claim in claims or ():
        phrase = _collapse(claim)
        if phrase and _phrase_pattern(phrase).search(haystack) and claim not in found:
            found.append(claim)
    return found
