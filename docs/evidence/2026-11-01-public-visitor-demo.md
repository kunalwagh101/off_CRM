# S-06.02.53 evidence, 1 November 2026 (IST)

Base develop c1c8a3736e735e941dba3f9a3b7ef7d090a0ae62. Owner requested a separate third-party visitor login displayed on sign-in. Private password was not present in recovered handoff; it was not changed or disclosed.

Test-first local RED: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py` produced 4 failed, 15 passed. Missing hint, read-only request boundary and storage separation were observed. Initial seed regression found list_campaigns returns (rows, total), fixed by checking rows. A timer assertion used a nonexistent RoutineService.status; corrected to verify its actual task remains absent.

Local GREEN: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py tests/test_workspace_isolation.py`: 49 passed in 15.88s. `npm test --prefix frontend`: 18 files / 213 passed. `npm run build --prefix frontend`: passed, existing large-chunk advisory. Critical Ruff: passed.

Baseline `uv run python scripts/verify_board.py --skip-tests` found one existing duplicate S-06.01.02 in BACKLOG and IN_REVIEW; removed obsolete BACKLOG entry, preserving review evidence (D-339). No other story status changed.

Implementation: api/public_demo.py dedicated empty-folder guard, explicit read allowlist, transactionally seeded fictional contacts; api/config.py opt-in setting; api/app.py public workspace bootstrap, protected credentials hint, scheduler disable, request guard; frontend login card, persistent visitor banner and CRM-only navigation. No new dependencies or database migrations.

Self-review only. Separate Render full regression, public service deployment, real browser checks and operational evidence pending. Story IN_REVIEW. General production durability/tenancy blockers are unchanged; this service contains disposable fictional data and no external integrations.

Public service creation via Render plugin: srv-dbj5m45g1s2s73er48l0, https://off-crm-visitor-demo.onrender.com, free Singapore, develop, auto-deploy off, fresh /tmp/offcrm-visitor-demo and no private integrations. First code deploy dep-dbj5mi67bikc73eg54g0 built but exited early before listening. D-340 records the startup failure. Public-demo container entrypoint now always selects run_offsetx_web.py and generates its private session secret internally. Local entrypoint TDD RED 1 failed/3 passed; GREEN 4 passed. The dashboard sign-in path was abandoned; all service actions use the connected Render plugin.

Git HTTPS reads worked but push had no write credential; published identical source tree via connected GitHub app, on develop only. Source commit 5a114d7959694b2db085d908164692054f5768b3; browser-test mobile locator corrected at 5e5039cee3b80c48efd8908d17343a7b93cf2edc. Full isolated review dep-dbj5mth42hec73c3jo8g running on that core implementation.
