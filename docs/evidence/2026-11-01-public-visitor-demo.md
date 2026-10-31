# S-06.02.53 evidence, 1 November 2026 (IST)

Base develop c1c8a3736e735e941dba3f9a3b7ef7d090a0ae62. Owner requested a separate third-party visitor login displayed on sign-in. Private password was not present in recovered handoff; it was not changed or disclosed.

Test-first local RED: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py` produced 4 failed, 15 passed. Missing hint, read-only request boundary and storage separation were observed. Initial seed regression found list_campaigns returns (rows, total), fixed by checking rows. A timer assertion used a nonexistent RoutineService.status; corrected to verify its actual task remains absent.

Local GREEN: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py tests/test_workspace_isolation.py`: 49 passed in 15.88s. `npm test --prefix frontend`: 18 files / 213 passed. `npm run build --prefix frontend`: passed, existing large-chunk advisory. Critical Ruff: passed.

Baseline `uv run python scripts/verify_board.py --skip-tests` found one existing duplicate S-06.01.02 in BACKLOG and IN_REVIEW; removed obsolete BACKLOG entry, preserving review evidence (D-339). No other story status changed.

Implementation: api/public_demo.py dedicated empty-folder guard, explicit read allowlist, transactionally seeded fictional contacts; api/config.py opt-in setting; api/app.py public workspace bootstrap, protected credentials hint, scheduler disable, request guard; frontend login card, persistent visitor banner and CRM-only navigation. No new dependencies or database migrations.

Self-review only. Separate Render full regression, public service deployment, real browser checks and operational evidence pending. Story IN_REVIEW. General production durability/tenancy blockers are unchanged; this service contains disposable fictional data and no external integrations.

Public service creation via Render plugin: srv-dbj5m45g1s2s73er48l0, https://off-crm-visitor-demo.onrender.com, free Singapore, develop, auto-deploy off, fresh /tmp/offcrm-visitor-demo and no private integrations. First code deploy dep-dbj5mi67bikc73eg54g0 built but exited early before listening. D-340 records the startup failure. Public-demo container entrypoint now always selects run_offsetx_web.py and generates its private session secret internally. Local entrypoint TDD RED 1 failed/3 passed; GREEN 4 passed. The dashboard sign-in path was abandoned; all service actions use the connected Render plugin.

Git HTTPS reads worked but push had no write credential; published identical source tree via connected GitHub app, on develop only. Source commit 5a114d7959694b2db085d908164692054f5768b3; browser-test mobile locator corrected at 5e5039cee3b80c48efd8908d17343a7b93cf2edc. Full isolated review dep-dbj5mth42hec73c3jo8g running on that core implementation.

## Live visitor acceptance

Replacement service with the standard Docker command (no custom override): `srv-dbj5q5vb9u1s73d4fe1g`, https://off-crm-public-demo.onrender.com/. Render deploy `dep-dbj5q6vb9u1s73d4fgo0` is LIVE on source `aaa0a59ac61ac40a47d4f0b1ed83b8ce39333789`, finished 2026-10-31T21:28:31.532453Z (1 November IST). First service `off-crm-visitor-demo` remains failed/inert, not the published link; the connector has no suspend/delete/start-command-edit action. No existing owner or QA app settings, data, passwords, main branch or paid resources were changed.

Real HTTPS acceptance on the live service PASS: unauthenticated session returns the public hint; dashboard refuses before login (401); advertised credentials authenticate to public-demo; one paused campaign and three fictional contacts; POST campaign creation refused (403); Notion/owner health refused (403); logout succeeds then dashboard returns 401; readiness returns 200. Verified live login screen in cloud Chromium: username/password displayed, inputs prefilled, sample/read-only notice visible. No private signing key is exposed. Service runtime logs show only method/route/status/timing, not credentials.

Isolated Render review at core source `5e5039cee3b80c48efd8908d17343a7b93cf2edc`: full SQLite 2838 passed / 45 skipped / 44 warnings in 276.48s; visitor Chromium PASS at 1440px and 390px (visible credentials, login, sample contacts, write refusal, logout). Frontend 213 PASS/build. Latest startup/auth/public tests locally: 28 passed in 7.17s; 49 auth/workspace/public tests previously passed. `uv run python scripts/verify_board.py --skip-tests`: OK after D-339, all 70 recorded commits on branch. This is structural verification; historical DONE evidence commands were not rerun by that command.

No schema migration or private-data persistence change. Sample data is intentionally disposable and automatically recreated on empty storage. Each container start generates a fresh private session signing secret, expiring old sessions. Rollback by withdrawing the dedicated public service; never disable the public mode flag on an accessible known account. No claim of full production readiness or independent penetration review. Final broad disposable PostgreSQL regression: 2858 passed / 94 skipped / 44 warnings in 355.68s. Focused PostgreSQL: 215 passed. The isolated image completed all test stages; publishing status is recorded separately below. S-06.02.53 stays IN_REVIEW for independent security/recovery review and exact-latest-source review evidence; the public demo itself is deployed and verified.

## Final test result

Render review `dep-dbj5mth42hec73c3jo8g` on core source `5e5039c`: SQLite **2838 passed / 45 skipped**, PostgreSQL **2858 passed / 94 skipped**, focused PostgreSQL **215 passed**, board-verifier unit tests **67 passed**, desktop/mobile visitor Chromium **PASS**. PostgreSQL summary observed at 2026-10-31T21:34:26.782030942Z. The later container entrypoint change at `aaa0a59` has four local targeted checks and real live Render startup/login/read-only/logout evidence; do not claim that startup file was included in the older review image's full suite. No production integration, private dataset, external email or provider was used. Existing production blockers remain separate.
