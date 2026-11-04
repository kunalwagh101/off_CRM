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

## Expanded-suite harness correction (D-370)

Isolated Render `dep-dblrkc6417fc73bbo5fg` on `99f5169` ran the expanded A10 gate: 11 passed, 1 failed, 1 PostgreSQL-only skipped. The single failure was the test double's phrase `billing status uncertain`, which correctly matched the application's terminal PAYMENT classifier. Corrected test-only source `8871aa7` to raise a genuine network timeout message. Neither application logic nor payment failure rules were changed. A new exact-source Render review must verify this corrected case.

## Final exact-source isolated regression checks — 2026-11-05 IST

- Pinned executable/test + documentation source: `822ffa8401d0d8ad1498a84e487fcd5f747b90a7`, isolated Render build `dep-dblrlb6i0phs7387c37g` on `off-crm-review-runner-20261015`. Last test-source change `8871aa7`; last runtime fixes `763a862` and `48e271`.
- RED/green followed the same real `EgressBroker.call` and adapter entry points, with **7 expected RED / 2 existing PASS** in `dep-dblrg5h5efls73aj916g`. The corrected source's expanded A10 early test gate **12 passed / 1 PostgreSQL-only skipped**. The PostgreSQL-only race case ran in the full PostgreSQL stage below.
- Full SQLite Python regression: **3,027 passed / 57 skipped / 44 warnings** from `uv run pytest -q` (review Docker step #60).
- Full disposable real PostgreSQL regression: **3,052 passed / 101 skipped / 44 warnings** from `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` (step #63), including `test_A10_real_postgres_two_workers_share_atomic_usd_budget`; focused PostgreSQL integration suite **215 passed**. No customer PostgreSQL instance used.
- Other Docker review gates passed by successful stage completion: frontend npm tests, TypeScript production build, npm audits, Ruff error/undefined-name gate, A05 identity, A09 Enter approval, A11 atomic quotas (14 early PASS / 1 PG-only skip), A12/A13 cache, A14 idempotency, A16 email provider recovery, A18 numeric claims, A20 media, A21 corrupt-image checks, 12 repeated concurrent SQLite writes, structural board verifier, Chromium desktop/mobile Contacts and Public Demo, real Chromium A09 and A18 probes.
- The structural board verifier used `--skip-tests` and **did not** replay historical DONE evidence. No live paid-provider account/invoice test, independent third-party penetration engagement, customer-account end-to-end acceptance or `main` promotion was performed. A10 remains partially verified and S-06.02.66 remains BACKLOG pending audit/production gates.

**The review image finished all QA build stages.** Its final service LIVE status must be verified separately against `dep-dblrlb6i0phs7387c37g`; a green image build is not proof of deployment completion.
