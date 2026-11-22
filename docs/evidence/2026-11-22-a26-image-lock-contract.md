# A26 — actual Docker production dependency lock parity

Feature: F-06.02. Story: S-06.02.23. Defect: D-509. Branch: `develop`.

## Risk

The September audit A26 found the image omitted SES and PostgreSQL extras and was not lock-reproducible. The source Dockerfile now installs `uv sync --locked --no-dev --extra email --extra postgres`, but the previous running-container smoke checked only HTTP readiness, static HTML and effective UID. That did not prove the bundled libraries matched the lock or could be imported.

## RED / GREEN evidence

In an isolated local Python test directory matching the repository module layout:

- **RED** — running the eight `test_audit_a26_image_dependencies.py` tests before adding the module stopped in collection with `ModuleNotFoundError: No module named 'scripts.qa.a26_image_dependency_contract'`; exit code 2.
- **GREEN** — the exact eight regression tests passed after creating the script: `8 passed in 0.07s`.
- The local proof is isolated. It does not substitute for the production image or the full repository tests.

## Production-image check

- The script executes inside the running Docker image, uses the selected app virtualenv, reads the actual `/app/uv.lock`, imports five runtime packages (boto3, psycopg, psycopg-binary, fastapi, uvicorn), and checks each installed version against `uv.lock`.
- Verifies that psycopg selects the binary libpq driver; `pytest`, `ruff` and `playwright` are absent from the release environment.
- No provider credentials, external API request or customer contact is needed; only package names and PASS/FAIL are printed.
- The container workflow's build, startup, A26 gate and restart stages must all pass on the same source. Existing GitHub CI must also pass. Both are pending at the time of this record.

## Limitations and release status

Image dependency parity is necessary but not sufficient for any production deployment. Live SES delivery, managed PostgreSQL connection, controlled external backup/recovery, supervised workers and independent penetration/customer acceptance remain OPEN. Render deployment remains blocked by build minutes. Keep A26 as verification pending until the Docker job completes; keep S-06.02.23 and F-06.02 IN_PROGRESS.

## Verified production Docker result (2026-11-22)

The [actual production-container workflow 45024963091](https://github.com/kunalwagh101/off_CRM/actions/runs/45024963091) built and started the image on source `0c42801`. All stages passed: production Docker build, health/frontend/unprivileged process, A26 dependency check, app restart and cleanup. The actual job log at 12:58:24 UTC says: `A26 PASS: 5 locked runtime distributions; binary SQL driver; no dev tools`. Exact-source five-job Python/PG CI for `0c42801` remained pending when this checkpoint was written; the documentation/A35 source change requires its own newer CI. Render customer acceptance remains **OPEN**.
