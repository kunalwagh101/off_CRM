"""Deterministic claim verification for autonomous browser findings.

A model saying a fact came from a page is not evidence.  S-11.02.03 checks the
model's claim against the page text off_CRM captured itself.  There is no model
call in this module and confidence never changes the answer.

Normalisation is intentionally conservative: Unicode compatibility forms,
typographic punctuation, case and whitespace may differ without changing a
claim.  Digits, word order and negation are never removed or rearranged.
"""

from __future__ import annotations

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


def normalize_claim_text(value: str) -> str:
    """Normalise presentation differences without changing the fact itself."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(_PUNCTUATION)
    return " ".join(text.casefold().split())


def verify_finding(
    finding: Finding,
    *,
    captured_text: str,
    capture_truncated: bool,
    available_findings: Mapping[str, Finding],
) -> str:
    """Return the verification state for one already source-bound finding.

    ``available_findings`` contains only findings that have already survived
    source binding and verification.  A derived finding may therefore depend on
    them without trusting the model's statement that its inputs were valid.
    """
    if finding.kind == "derived":
        if not finding.inputs or finding.field in finding.inputs:
            return DERIVED_UNVERIFIED
        if any(name not in available_findings for name in finding.inputs):
            return DERIVED_UNVERIFIED
        return SUPPORTED

    haystack = normalize_claim_text(captured_text)
    value = normalize_claim_text(finding.value)
    quote = normalize_claim_text(finding.source.quote)
    if value and quote and value in haystack and quote in haystack:
        return SUPPORTED
    if capture_truncated:
        return TRUNCATED
    return UNSUPPORTED
