# S-06.02.66 / A10 — paid AI usage receipt integrity

## Scope and security boundary
The original production audit A10 found paid-provider calls accounted as USD 0 and a spend limit that never stopped requests. Current develop already has atomic reservations from A11/S-06.02.60 and an earlier cost-ledger repair; this work isolates a remaining gap in **untrusted provider token receipts**, not an unrelated rewrite.

Files: `offsetx_apollo_builder/outreach/providers.py::read_usage`, `offsetx_apollo_builder/ai/broker.py::measure`, `tests/test_ai_billing_integrity_a10.py`, `Dockerfile.review`. One broker egress gate and existing durable quota locks are preserved.

## Executed TDD RED (2026-11-05 IST)
- Test-only source `32037e5`, review-gate source `1f4f9b92668eeb006ee1d7f7bebc42ae6877e75d`.
- Render isolated review `dep-dblrg5h5efls73aj916g`, step #27:
  `uv run pytest -q tests/test_ai_billing_integrity_a10.py`
  **7 failed, 2 passed**, expected. The real `EgressBroker.call` accepted `last_usage={"tokens_in":0,"tokens_out":0}` as provider-confirmed free; malformed strings/NaN could raise after transport. The real `read_usage` parser accepted false zero/boolean counts and raised OverflowError on infinity. Valid paid token receipts and legitimate zero-output receipts already passed.

## First verified GREEN
- Fix source `763a862bde09bb6359c5d31e011dd67255327c0e` (`read_usage`) and `48e27119bcbfa93934d5446b94bd1473e59e8a02` (`measure`).
- Isolated Render `dep-dblrgs2jnfac73d9g7ug` step #27: same focused command **9 passed** on exact source `48e271`. It rejects zero, nonfinite, boolean, malformed/negative receipts, preserves legitimate input-only usage, persists priced spend, and prevents a second unaffordable paid-provider call after a broker restart.
- A subsequent source `0054e34` / `839fc67` adds failed-provider accounting, two independent local/hosted SQLite workers and disposable PostgreSQL workers racing over one USD limit. These additional tests are not counted as PASS until a later source-bound review runs.

## Rollback, operational limits and remaining QA
No schema migration, new dependency, paid API call, secrets access or customer deployment. A rollback must retain the quota ledger and stop live paid requests before reverting either validation path; reverting without mitigation reopens D-369. Existing reservation/reconcile code remains unchanged.

Full SQLite and PostgreSQL regression, source-bound Render LIVE status, Chromium, independent penetration, real paid-provider invoices/unknown provider pricing, full-history board replay and customer account acceptance are separate gates. Keep A10 partially rechecked under S-06.02.23, and S-06.02.66 out of DONE.
