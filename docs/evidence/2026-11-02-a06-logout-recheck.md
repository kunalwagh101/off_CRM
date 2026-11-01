# A06 session revocation recheck — 2026-11-02

**Status:** QA running; not a certification. **Audit:** S-06.02.23 / A06. **Branch:** develop. **Test-source commit:** `37a6d2f7bc13f4d59a450b381d92c7ce7a825912`.

## What changed

The pre-existing `tests/test_api_auth.py::test_logout_revokes_copied_cookie_even_after_application_restart` already covers cookie replay after logout and restart. A new test, `tests/test_api_auth.py::test_api_logout_revokes_only_current_session`, covers the missing API-level two-login isolation: a logout must invalidate its own token, refuse replay, but preserve another valid login for the same user. This is a recheck of the historical A06 finding, not a new claim of a vulnerable implementation.

## Tests and external evidence

- Render workspace: Kunal Wagh's Workspace (`tea-cspt7hggph6c739lq5j0`)
- Isolated review service: `srv-db86p4u89jmc73cehns0` (`Dockerfile.review`, auto-deploy off)
- Exact QA source: `37a6d2f7bc13f4d59a450b381d92c7ce7a825912`
- Render deployment: `dep-dbjp60etlv9c73dt6sng`
- Last observed state at documentation time: `build_in_progress`; results not yet verified
- Defined targeted command: `uv run pytest -q tests/test_api_auth.py`
- Broader review runner: frontend test/build and audit, Python Ruff, targeted API/auth and other gates, full SQLite pytest, isolated PostgreSQL full pytest, Chromium desktop/mobile. Each gate only counts as passed after actual logs confirm it.

No runtime code, storage or schema change was made. Customer/main deployments were not triggered. This alone does not cover a real authenticated production login, cross-host hosted-DB replay or independent penetration, and does not close the other 34 audit findings. The project board remains S-06.02.23 IN_PROGRESS. S-06.02.40 is BACKLOG, not deployed, pending durable queue and runtime/cost decisions.

## Follow-up

Read the deployment status and complete build log, record actual pass/fail counts and update A06 in the original audit table only after evidence supports it. For a failing regression, add an open defect and preserve the RED behaviour in the remediation work order; do not silently claim closure.

## Observed isolated review gates (2026-11-02)

Dockerfile.review on commit `37a6d2f7bc13f4d59a450b381d92c7ce7a825912`, Render deployment `dep-dbjp60etlv9c73dt6sng`, ran the early authentication/public-demo gate and reported **34 passed, 1 warning**. This includes the two A06 logout regression tests. A separate export/contact gate reported **19 passed, 1 warning**, including the three `tests/test_spreadsheet_exports.py` A19 regressions and the authenticated 503-contact pagination A23 regression. Storage-readiness 7 passed, agent permissions/run 44 passed, health 7 passed, inventory 2 passed, and the twelve repeated concurrency checks each passed. These are directly observed in Render build logs on the pinned source.

The audit index marks the tested A06, A19, A23 local/isolated behaviours closed; **this is not full production certification**. At this checkpoint the full SQLite and PostgreSQL suites, Chromium, overall review deployment success and independent live penetration remain unverified. S-06.02.23 continues IN_PROGRESS; all other findings retain their original status. Do not count this checkpoint as a full suite pass.

## Full isolated Render review results on test source 37a6d2f (2026-11-02 IST)

Direct Render build-log observations from `dep-dbjp60etlv9c73dt6sng`:

- Frontend npm tests, production build and configured dependency-audit stages reached their green Docker stages; no separate live user acceptance is claimed.
- Targeted authentication/public demo: **34 passed, 1 warning** (includes A06 new and existing tests).
- Targeted spreadsheet/contact/enrichment: **19 passed, 1 warning** (includes A19 and A23 regressions).
- Storage readiness: **7 passed**; agent permissions/run: **44 passed**; operational health: **7 passed**; storage inventory: **2 passed**; typed API body: **1 passed**; verifier-unit tests: **67 passed**; concurrency repetition: **12/12 passed**.
- Full SQLite Python: **2,848 passed, 45 skipped, 44 warnings**, about 4m53s.
- Isolated real Chromium Contacts: **PASS at 1280px and 390px**, including 503 persisted contacts, all six pages, last row, search and controls.
- Isolated real Chromium visitor demo: **PASS at 1440px and 390px**; login, provider setup, sample contacts, write refusal and logout.
- Real disposable PostgreSQL targeted suite: **215 passed, 1 warning**.
- Full disposable PostgreSQL Python: **2,868 passed, 94 skipped, 44 warnings**, about 6m11s.
- Full Docker QA gates and image export completed successfully in the observed build log. The Render deployment status at the most recent deployment-status poll was still `build_in_progress`; do not call it LIVE without a separate status observation.

These test cases recheck specific A06/A19/A23 behaviours, not the 35-finding production audit. Remaining issues include live customer authentication/worker, full-history board verifier, independent penetration, external providers and the unresolved durable mail worker. S-06.02.23 stays IN_PROGRESS, and S-06.02.40 is still BACKLOG. No customer production or `main` promotion.

## Final isolated review deployment state

Render connector confirmed isolated review deployment `dep-dbjp60etlv9c73dt6sng` on exact test source `37a6d2f7bc13f4d59a450b381d92c7ce7a825912` reached **LIVE** at **2026-11-01T19:46:27.662103Z** (2026-11-02 01:16:27 IST). This service is the Docker QA marker, not the customer `off-crm` or public visitor application. All listed test and browser stages passed before the marker became LIVE. No customer-facing service was redeployed. The three audit findings have scoped regression evidence, but S-06.02.23 still requires the other findings, full-history board verifier and independent production/security acceptance before DONE.
