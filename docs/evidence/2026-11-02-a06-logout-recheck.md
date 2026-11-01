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

## Observed isolated review gates (2026-11-01)

Dockerfile.review on commit `37a6d2f7bc13f4d59a450b381d92c7ce7a825912`, Render deployment `dep-dbjp60etlv9c73dt6sng`, ran the early authentication/public-demo gate and reported **34 passed, 1 warning**. This includes the two A06 logout regression tests. A separate export/contact gate reported **19 passed, 1 warning**, including the three `tests/test_spreadsheet_exports.py` A19 regressions and the authenticated 503-contact pagination A23 regression. Storage-readiness 7 passed, agent permissions/run 44 passed, health 7 passed, inventory 2 passed, and the twelve repeated concurrency checks each passed. These are directly observed in Render build logs on the pinned source.

The audit index marks the tested A06, A19, A23 local/isolated behaviours closed; **this is not full production certification**. At this checkpoint the full SQLite and PostgreSQL suites, Chromium, overall review deployment success and independent live penetration remain unverified. S-06.02.23 continues IN_PROGRESS; all other findings retain their original status. Do not count this checkpoint as a full suite pass.
