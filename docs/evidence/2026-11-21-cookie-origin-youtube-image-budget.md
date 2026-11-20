# Follow-through: D-463, D-456 and partial D-457 (2026-11-21)

Source: `kunalwagh101/off_CRM`, branch `develop`.

## What was found
- CI of the previous image/backup fixes failed because a new D-463 test expected the raw structured YouTube exception body. The middleware deliberately replaced a reported exception with an operator-safe string and error ID. The app previously showed generic text instead of the exact missing setup step.
- Cookie-authenticated API writes had no Origin or Fetch Metadata check. SameSite=strict and JSON-only routes are strong primary guards, but this left unnecessary exposure to same-site cross-origin requests.
- The text broker already checked a global monotonic deadline before switching models. Image failover did not: repeated slow failures could launch still more models after the time budget.

## Changes, with tests committed before production code
- **D-463:** `tests/test_e2e_findings_2026_11_13.py` now tests missing-key sweep and channel watch. Endpoint preflight returns a fixed JSON 422 naming `OFFSETX_YOUTUBE_API_KEY`; existing provider-exception catch and redaction remain unchanged. RED `2ceb621`, source `115e07c`.
- **D-456:** `tests/test_api_auth.py` tests foreign origins, a null/malformed origin, changed port/scheme, malicious Sec-Fetch-Site, successful same-origin/logout, local development and API token. Middleware checks cookie-authenticated unsafe methods only. RED `26c6264`, source `5b87127`, fixture correction `da7877a`.
- **D-457 (partial):** `tests/test_ai_model_selection.py` uses a simulated clock to prove a slow first image provider cannot launch a second after deadline expiry. RED `fa90ea3`, source `8eb8bca`.

## Acceptance not claimed
- Latest HEAD complete Python matrix, real PostgreSQL/PgBouncer, frontend, browser and container runs need observed success.
- A live browser test must check hosted reverse proxy Origin and local Vite behavior. No independent penetration test has run for these changes.
- An image call already in flight may still exceed the deadline; no unsafe thread cancellation or duplicate external call is introduced.
- D-451 cross-workspace CRM exposure and legacy cutover is still the critical release blocker. Real offsite S3 recovery, customer credentials and production deployment were not executed.
