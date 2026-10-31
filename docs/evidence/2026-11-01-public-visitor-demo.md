# S-06.02.53 evidence, 1 November 2026 (IST)

Base develop c1c8a3736e735e941dba3f9a3b7ef7d090a0ae62. Owner requested a separate third-party visitor login displayed on sign-in. Private password was not present in recovered handoff; it was not changed or disclosed.

Test-first local RED: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py` produced 4 failed, 15 passed. Missing hint, read-only request boundary and storage separation were observed. Initial seed regression found list_campaigns returns (rows, total), fixed by checking rows. A timer assertion used a nonexistent RoutineService.status; corrected to verify its actual task remains absent.

Local GREEN: `uv run pytest -q tests/test_public_demo.py tests/test_api_auth.py tests/test_workspace_isolation.py`: 49 passed in 15.88s. `npm test --prefix frontend`: 18 files / 213 passed. `npm run build --prefix frontend`: passed, existing large-chunk advisory. Critical Ruff: passed.

Baseline `uv run python scripts/verify_board.py --skip-tests` found one existing duplicate S-06.01.02 in BACKLOG and IN_REVIEW; removed obsolete BACKLOG entry, preserving review evidence (D-339). No other story status changed.

Implementation: api/public_demo.py dedicated empty-folder guard, explicit read allowlist, transactionally seeded fictional contacts; api/config.py opt-in setting; api/app.py public workspace bootstrap, protected credentials hint, scheduler disable, request guard; frontend login card, persistent visitor banner and CRM-only navigation. No new dependencies or database migrations.

Self-review only. Separate Render full regression, public service deployment, real browser checks and operational evidence pending. Story IN_REVIEW. General production durability/tenancy blockers are unchanged; this service contains disposable fictional data and no external integrations.
