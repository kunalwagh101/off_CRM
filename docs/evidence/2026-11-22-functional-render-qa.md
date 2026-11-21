# 2026-11-22 — real Render functional QA and public-boundary smoke

## Verified environment

- Repository: `kunalwagh101/off_CRM`; development branch: `develop`.
- New Render connection: `waghkunal1997@gmail.com`, workspace `tea-dbvlna40916s73bhp650`.
- **Functional web service** `srv-dc0vbd8m7kps73di4pm0`: `https://off-crm-functional-qa-20261122.onrender.com`, Dockerfile `./Dockerfile`, free plan, Singapore, branch `develop`, autoDeploy off.
- Initial functional deploy `dep-dc0vbdom7kps73di4r00` at `acf0432df535f1e95aabc2a3317b95b33435b7d9` reached **live**. Container started Uvicorn; Render GET `/` returned 200. This uses a QA-only demo login with nontrivial secrets stored only in Render Environment; do not publish those secrets.
- **Review test service** `srv-dc0o7e61egvs738i1920` remains separate. Its `Dockerfile.review` launches a synthetic QA marker after tests; it is **not** the functional CRM.

## RED → GREEN checks

- Test source commit `3ebb40139ae4c850943e9e6c63bfaa91fb8c9628`: `tests/test_render_functional_smoke.py` and deliberately unimplemented `scripts/live/remote_render_smoke.py` contract. Running these exact test cases in an isolated local Python 3 environment returned **10 expected failures**.
- Implementation/workflow commit `8433d0e7307e0bc73b24ad2d7faec2d73df8a384` implements strict HTTPS onrender.com URL validation, bounded HTTP reads, a safe public health/auth check, and controlled error output. Running the identical isolated unit checks after the implementation returned **10 passed**. The local verified script's Git blob SHA was `1c159b291aac510fda4f39459f255e7d28ad772a`, matching the committed blob.
- External GitHub Actions run [44943657458](https://github.com/kunalwagh101/off_CRM/actions/runs/44943657458) succeeded on `8433d0e`. Its decoded job log explicitly reported **RENDER QA PASS: 5 checks: root, ready, anonymous_session, private_dashboard, wrong_login**.
- Independent Render application access logs at 2026-11-21 19:57:17–19:57:19 UTC confirm actual network calls: `GET /` 200; `GET /health/ready` 200; `GET /api/v1/auth/session` 200 unauthenticated; `GET /api/v1/dashboard` 401; `POST /api/v1/auth/login` with known-invalid synthetic credentials 401. No real customer account, provider key, CRM mutation, send or publish was used.

To rerun only this bounded public-host probe:

```sh
python3 scripts/live/remote_render_smoke.py --base-url https://off-crm-functional-qa-20261122.onrender.com
```

The workflow can be run using its manual `workflow_dispatch` trigger. It intentionally does **not** attempt a valid login, save customer data, export mail, call external providers or validate actual UI interactions.

## Durability and production blockers

- The functional test service uses `/tmp/offsetx-qa/local_data`; its local files and database are disposable across Render restart/idle. Never use it for real customer data.
- New workspace already has a single free PostgreSQL database assigned to `offsetx-demo`. Attempting to create a second isolated free PostgreSQL instance for off_CRM returned Render HTTP 400: **cannot have more than one active free tier database**. We deliberately did not share OffsetX's customer database or buy a paid plan.
- Offsite hosted CRM backup `S-06.03.04`: owner selected independent encrypted S3-compatible storage (Q-29 answered), but an actual separate bucket, restricted credential, retention schedule, independent key custody and empty-DB recovery drill have not been configured or verified.
- CRM tenancy `S-06.01.06`, broader September audit `S-06.02.23`, supervised email worker `S-06.02.40`, entire S-06.03.06 durable store inventory and full F-04.01 paid-provider/role acceptance remain open. No production/customer deployment, independent penetration clearance, real mail or social publish is claimed.
- A separate full GitHub suite `44943657337` was started for the new test script; record its **actual** status separately. A successful public-host smoke is not a substitute for the full suite.

**Release state:** Test instrumentation delivered on `develop`. The three parent feature areas remain **NOT DONE** until every nested requirement and external acceptance gate is satisfied.

## 2026-11-22 — malformed-port smoke URL regression

The trusted-host check itself raised an uncaught `ValueError` on `https://qa.onrender.com:invalid-port`. Added a parametrised invalid-port input and ran the existing test file in a disposable local Python environment: **1 expected failure / 10 passes** against the original parser; removed the redundant `parsed.port` read because the stricter `parsed.netloc != parsed.hostname` rule already denies any port. The same suite then reported **11 passed**. Source blobs for the corrected script and test are `4010e43f64c88f76d806deb541ebeb439b2e42c8` and `c7ea978f194d1ae3abf068a2ffefa27c7d4ac3b2`. Re-run the remote workflow and full CI on the final merge commit before claiming release evidence.

## Existing agent-team Chromium QA on the same release code

Render review deploy `dep-dc0u8t3rjlhs73an2nfg` independently ran `scripts/live/review_agent_team_browser.py`. Build logs explicitly show PASS at **1280 px and 390 px** for owner profile/procedure CRUD, approval-scoped memory, role prerequisites, child bounds, deletion and read-only Scout. This happened inside the disposable Docker QA image, not through the public functional-host login. It cannot close F-04.01's real provider, media, cross-workspace or external-account gates.

## Short-window operational checks

Render request-log query for HTTP 5xx on the functional QA service, 2026-11-21 19:50:49–20:05:30 UTC, returned **zero matching requests**. Service metrics for 19:50–20:06 UTC showed reported memory usage around 112.6 MB at idle startup and 131.3 MB following the live smoke (bytes as reported by Render); CPU utilisation stayed low. This is an idle/light-traffic snapshot, **not** a stress, concurrency, persistence or long-term memory-leak test.
