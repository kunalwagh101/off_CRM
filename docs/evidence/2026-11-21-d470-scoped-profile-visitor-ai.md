# D-470 — Temporary CRM boundary narrowly corrected (2026-11-21)

Repo: kunalwagh101/off_CRM, develop, base 883ad812. Pre-fix GitHub Actions 44836755927 had 28 failed/3324 passed on Python 3.12 and 28 failed/3435 passed with PostgreSQL. The board verifier failed S-06.02.31's command with 17 failures. Existing profile and visitor AI tests received a 403 from D-451.

Scope: only owner-checked encrypted provider-profile APIs and the dedicated sample-only public-demo AI plan/run exemption; provider-call history, campaigns, drafts, customer AI and all other shared CRM routes remain denied. Added D-470 signed-in beta API regression that proves own profile operations and continued 403 on campaigns/provider-calls. Existing `tests/test_public_demo_ai.py` contains the sample AI regression.

After this change, require real `uv run pytest -q`, PostgreSQL suite, `uv run python scripts/verify_board.py`, frontend tests/build, independent penetration and customer/browser acceptance. No green result is asserted before evidence arrives. D-451 runtime tenancy/legacy manifest/worker isolation remains unfinished. No Render change or production deployment.
