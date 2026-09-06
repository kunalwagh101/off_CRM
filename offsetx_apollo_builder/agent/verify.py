"""Deterministic claim verification for autonomous browser findings.

A model saying a fact came from a page is not evidence. S-11.02.03 checks the
model's claim against the page text off_CRM captured itself. There is no model
call in this module and confidence never changes the answer.

Normalisation is intentionally conservative: Unicode compatibility forms,
typographic punctuation, case and whitespace may differ without changing a
claim. Digits, word order and negation are never removed or rearranged. Token
boundaries matter, so ``42`` does not match ``420``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from .result import Finding

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
TRUNCATED = "truncated"
DERIVED_UNVERIFIED = "derived_unverified"

_PUNCTUATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u00a0": " ",
    }
)
_NEGATIONS = frozenset(
    {
        "not",
        "no",
        "never",
        "without",
        "isn't",
        "isnt",
        "wasn't",
        "wasnt",
        "aren't",
        "arent",
        "weren't",
        "werent",
        "doesn't",
        "doesnt",
        "didn't",
        "didnt",
        "cannot",
        "can't",
        "cant",
    }
)


def normalize_claim_text(value: str) -> str:
    """Normalise presentation differences without changing the fact itself."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_PUNCTUATION)
    return " ".join(text.casefold().split())


def _span_pattern(needle: str) -> re.Pattern[str]:
    """Match a normalised span without allowing it inside a larger token."""
    escaped = re.escape(needle)
    left = r"(?<!\w)" if needle and needle[0].isalnum() else ""
    right = r"(?!\w)" if needle and needle[-1].isalnum() else ""
    return re.compile(left + escaped + right, flags=re.UNICODE)


def _preceding_token(text: str, start: int) -> str:
    prefix = text[:start].rstrip()
    if not prefix:
        return ""
    match = re.search(r"([^\s]+)$", prefix)
    return match.group(1).strip(".,;:!?()[]{}\"'") if match else ""


def _contains_span(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return _span_pattern(needle).search(haystack) is not None


def _contains_supported_value(context: str, value: str) -> bool:
    """Find an exact-token claim without silently erasing nearby negation."""
    if not context or not value:
        return False
    value_starts_negated = (value.split(" ", 1)[0] if value else "") in _NEGATIONS
    for match in _span_pattern(value).finditer(context):
        previous = _preceding_token(context, match.start())
        if not value_starts_negated and previous in _NEGATIONS:
            continue
        return True
    return False


def verify_finding(
    finding: Finding,
    *,
    captured_text: str,
    capture_truncated: bool,
    available_findings: Mapping[str, Finding],
) -> str:
    """Return the verification state for one already source-bound finding.

    ``available_findings`` contains only findings that have already survived
    source binding and verification. A derived finding may therefore depend on
    verified observed inputs without trusting the model's statement that its
    inputs were valid. Derived arithmetic/summary semantics are deliberately not
    guessed here: the result remains labelled ``derived`` and is accepted only
    when every declared input is an already verified observed finding.
    """
    if finding.kind == "derived":
        if not finding.inputs or finding.field in finding.inputs:
            return DERIVED_UNVERIFIED
        if any(name not in available_findings for name in finding.inputs):
            return DERIVED_UNVERIFIED
        if any(available_findings[name].kind != "observed" for name in finding.inputs):
            return DERIVED_UNVERIFIED
        return SUPPORTED

    haystack = normalize_claim_text(captured_text)
    value = normalize_claim_text(finding.value)
    quote = normalize_claim_text(finding.source.quote)

    # The quote is the model's claimed supporting span. It must itself exist in
    # the host-owned capture. If the capture was cut before that span, report an
    # inconclusive truncation rather than calling the model a liar.
    if not _contains_span(haystack, quote):
        return TRUNCATED if capture_truncated else UNSUPPORTED

    # Once the quote is present, truncation is irrelevant: the quoted evidence
    # either supports this exact value or it does not. Requiring the value inside
    # the quote prevents a model from citing one sentence while borrowing a
    # convenient value from an unrelated part of the same page.
    if _contains_supported_value(quote, value):
        return SUPPORTED
    return UNSUPPORTED
