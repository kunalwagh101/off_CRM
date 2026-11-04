# A16 / D-363 — Email provider setup failure: reproducible RED and focused GREEN

**Date:** 2026-11-04 UTC. **Repository:** `kunalwagh101/off_CRM`. **Branch:** `develop`. **Story:** `S-06.02.61` (BACKLOG while audit/deployment prerequisites remain).

## Actual RED
- **Test-only source:** `61cc4fa40a56270af8dd8e2041a655a05a06982a`.
- **Isolated Render QA:** `dep-dbldu5bncjis73djca20`; status `build_failed`.
- Exact early gate: `uv run pytest -q tests/test_email_delivery.py -k A16` produced **5 failed, 16 deselected** (5 distinct parameterised cases).
- All failed because `provider_factory` raised after claiming a job, outside the send error handler. The worker returned no safe result and could strand the persisted job as sending. The failure trace in Render identifies `outreach/deliverability/service.py:356`. The test fixtures used synthetic contacts and no real providers.

## First GREEN
- **Implementation source:** `144e1cbb1bb604fdf93f82fe08f4ea4ae899dae8`.
- **Isolated Render QA:** `dep-dbldur942hec73fvgeq0`.
- Same exact early gate produced **5 passed, 16 deselected**.
- The worker now catches factory exceptions before send. Unknown or permanent setup errors get a terminal `failed` state; a retryable setup error produces a bounded `retry_wait` and may succeed after a restart; after the fifth attempt it becomes failed. Failures return one safe error reference and do not leak a synthetic secret string. An unrelated queued job still executes.
- The existing separate send-time handler preserves `delivery_unknown` for ambiguous post-send outcomes. Existing mail tests must also pass in the broad suite.

## QA and release boundary
- Full SQLite / disposable PostgreSQL, independent penetration, actual SES/broker/provider credentials and supervised durable worker deployment are separately required. At this checkpoint broader Render QA is running; **no full-suite success is asserted**.
- The Render QA marker is not a customer service and must not send email.
- No production keys, customers, migrations or customer deployments were touched. No change to `main`.
- The board remains BACKLOG under S-06.02.23 audit and S-06.02.40 durable worker dependencies, despite build-ahead code.
- Rollback: never revert without stopping the worker and reconciling outstanding claimed jobs; the old code is unsafe on the same state. Keep historical evidence and existing jobs.

## Final observed Render review verdict — 2026-11-04

The early GREEN report above was followed by the **completed full build** on the same exact source `144e1cbb1bb604fdf93f82fe08f4ea4ae899dae8`. Render `dep-dbldur942hec73fvgeq0` became **LIVE at 2026-11-04 07:52:04 UTC**. The review image is a QA success marker only, not the customer app.

| Gate | Observed result |
|---|---|
| RED pre-fix | 5 failed on 61cc4fa, deploy dep-dbldu5bncjis73djca20 build_failed |
| A16 TDD GREEN | 5 passed, 16 deselected |
| Full SQLite Pytest | 2,970 passed, 54 skipped, 44 warnings |
| Full real PostgreSQL Pytest | 2,993 passed, 100 skipped, 44 warnings |
| Focused real PostgreSQL | 215 passed |
| Verifier-unit suite | 67 passed |
| Concurrency | 12/12 repeated tests passed |
| Structural board check | PASS using `--skip-tests`; no full-history evidence replay |
| Frontend, static and npm security audits | Completed mandatory Docker review stages |
| Chromium browser | Desktop/mobile Contacts and public demo PASS, keyboard and numeric browser gates PASS |

**Limits:** No independent penetration certification, no real SES/provider account acceptance, no externally supervised email worker and no customer/main deployment. Worker deploy story S-06.02.40 and audit S-06.02.23 remain unfinished. Design constraint DD-140: provider factory construction must never itself send messages. Source 144e1cb is the tested code; later changes in this history are documentation, not new app changes.
