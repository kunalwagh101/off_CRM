# Production integration verification

This is an audit harness for application commit
`9f71f3c07f32407857311a1c4ed756925a612e6d`. It changes tests and CI only.
Application defects should fail the checks and be recorded, not worked around.

The workflow provisions a disposable PostgreSQL 16 service, requires an actual
Docker daemon and installed Chrome, and runs all existing tests with their live
integration settings. It then exercises all 18 frontend screens, campaign
creation/pause/persistence, CSV import/persistence, and login/refresh/logout.
The extra browser test dependency is pinned to Playwright 1.61.0. Chrome's own
sandbox stays enabled; the runner must be an ordinary user.

Container checks prove that code actually starts, confirm its UID/capabilities,
check writable output, read-only boundaries and absence of the private store,
and compare network denial with a working connection to a disposable control
container. A container launch failure cannot count as successful isolation.
The Python image's immutable digest is resolved before use and saved alongside
actual PostgreSQL, Docker, Python and Chrome versions. No image is pulled by the
application sandbox itself.

Run the workflow on the audit branch. Missing infrastructure, skipped tests,
missing reports and failed assertions all fail the job. XML results, runtime
versions, screenshots and browser errors are saved even on failure.

For an equivalent local run on a machine with Docker and Chrome:

1. Create a disposable PostgreSQL database and export
   `OFF_CRM_TEST_POSTGRES_URL`. Never use a customer database: the existing
   backend tests drop tables.
2. Install dependencies with `uv sync --extra dev --extra email --extra postgres
   --locked`, then `uv pip install playwright==1.61.0`.
3. Run `npm ci` and `npm run build` in `frontend/`.
4. Pre-pull a Python 3.12 image; export `OFF_CRM_SANDBOX_TEST_IMAGE` as its
   `python@sha256:...` digest and `OFF_CRM_LIVE_EVIDENCE` as an existing absolute
   output directory.
5. Run `uv run --no-sync pytest tests verification/test_live.py -q -ra
   --junitxml=live-results.xml`. Confirm zero skipped tests.

All data is synthetic. This harness sends no emails, creates no social posts,
uses no provider credentials and does not certify a production deployment.
Authenticated provider acceptance needs the application's configured test
accounts. An app connector's successful profile request proves that connector's
authentication, not the application's separate API adapter.
