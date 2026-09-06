# S-11.02.03 — Claim verification boundary

This story closes the trust gap between **having a real source** and **returning a true observed value**.

For schema-bearing autonomous browser runs, off_CRM now applies these boundaries in order:

1. The caller owns the allowed output field names.
2. The model may propose a value, source step id, quote, kind and confidence.
3. off_CRM resolves URL, timestamp, screenshot and captured text from its own append-only trace.
4. Deterministic host code verifies an observed value against the cited captured page text.
5. Only a field that survives those checks enters `RunOutcome.findings` and the CRM-friendly `RunOutcome.record` projection.

## Observed findings

Verification is deliberately conservative and contains no model call.

- Unicode compatibility forms, typographic punctuation, case and whitespace may normalise.
- Token boundaries remain meaningful: `42` does not verify against `420`.
- Word order is not rearranged.
- Immediate negation is not erased: `profitable` is not accepted from `not profitable`.
- The supporting quote must exist in the host-owned page capture.
- The value must be supported inside that quote; a value elsewhere on the page cannot borrow an unrelated quote.
- Model confidence is audit metadata only and cannot override a failed check.

An unsupported observed field is dropped and traced as `result_field_unsupported`.

## Derived findings

A derived result is explicitly labelled `kind=derived` and names its input fields. Every named input must already be a verified, source-bound finding. An opaque or unverified intermediate value is refused as `result_field_derived_unverified`.

This story does **not** invent a universal arithmetic or summarisation language. The result remains visibly labelled `derived`; the verifier proves its declared inputs, not an undeclared hidden calculation.

## Truncated captures

`Page.read` is bounded by `MAX_READ_CHARS`. When the cited supporting span is absent from a capture that was cut, off_CRM reports the field as unverified due to truncation rather than asserting that the model invented it. The field is still not returned.

## Proof gates

`tests/test_agent_claim_verification.py` covers:

- case/whitespace normalisation;
- `42` versus `420`;
- immediate negation;
- unrelated supporting quotes;
- truncated evidence;
- derived inputs;
- a real Chromium page where a plausible high-confidence unsupported number is refused.
