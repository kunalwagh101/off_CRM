# S-06.02.51 — Video request-stream guard: executed Render QA, 2026-10-30

## Exact source and QA runner

- **Tested application commit:** `71fb99c554bf7d566ad6ad27e921c214c339884c` on `kunalwagh101/off_CRM/develop` (the guard code and AnyIO test-runner follow-up).
- Render workspace: Kunal Wagh's Workspace; **isolated test-only review runner** `srv-db86p4u89jmc73cehns0`, deploy `dep-dbhqq2u1egvs7388ool0`, Dockerfile.review.
- Previous preliminary deploy `dep-dbhqpgbbc2fs73f5p4ig` on `8e3a676` was **cancelled** when the corrected AnyIO test commit was pushed; its incomplete outcome is not evidence.
- Status when this ledger was written: test-backed QA image build stages all PASSED, image cache export in progress; final Render `LIVE` status is **not claimed** until separately observed. No customer-facing/production service was deployed.

## Test results from actual Render build logs

| Gate | Observed |
|---|---|
| New upload-stream/ASGI adversarial cases `tests/test_video_upload_body_guard.py` | 11 cases included in and passed with both full Python suites |
| `uv run pytest -q` (full SQLite mode) | **2777 passed, 45 skipped, 44 warnings, 254.01s** |
| `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` (disposable PostgreSQL) | **2797 passed, 94 skipped, 44 warnings, 321.11s** |
| Existing targeted PostgreSQL storage/CRM/media tests | **215 passed, 1 warning** |
| Pre-PostgreSQL logout/session revocation test | 1 passed, 1 warning |
| Existing CRM contact/import/export regression | **19 passed, 1 warning** |
| Workspace context security tests | 3 passed |
| Deterministic CRM cursor lock | 1 passed |
| API concurrency/restart repetition | **12/12 passed** |
| CI/board verifier regression files | **67 passed** (NOT equivalent to full-history `scripts/verify_board.py`) |
| Ruff broken-name/syntax gate | **All checks passed** |
| Frontend test/build and npm audit gates | **Passed as prerequisites for the backend and QA stages**; the dependency tree still has known moderate Vitest dev advisories (D-321) |
| Real Chromium Contacts flow | **PASS desktop 1280 px and mobile 390 px**, 503 contacts, 6 pages, search |

11 new tests increased the SQLite and PostgreSQL passing totals from 2766/2786 to **2777/2797**. The ASGI tests use a real FastAPI TestClient for both authenticated video endpoints and a low-level receive/send harness to exercise chunked overflow, slot exhaustion, idle timeout and temporary-file cleanup. A separate local independent FastAPI prototype was written test-first and reached **11 passed**, but this is not a substitute for the above actual repository runs.

## Security controls delivered

- Both video import and render routes reject request bodies at the ASGI receive boundary before multipart parsing can consume unbounded resources: configured `OFFSETX_MAX_UPLOAD_BYTES + 16 KiB` request overhead. The per-file `read(limit + 1)` remains in the handlers.
- Large Content-Length claims are denied early, while bogus small claims cannot override actual byte counting. Invalid headers fail closed.
- Temporary payload spool stays at or below 256 KiB in Python heap before rolling over to a private auto-closed OS temp file. At most two in-flight uploads per app process. A stalled sender's next chunk times out after 30 seconds; disconnect/cancellation/failure closes the temporary file and releases the upload slot.
- Unauthorized requests still must pass the existing application authentication; unrelated routes are unchanged.

## Limits, unresolved issues, and rollback

1. **S-06.02.51 remains IN_REVIEW, A15 partially mitigated.** App-process concurrency is limited, not global across multiple replicas; no reverse-proxy-wide request body cap, slowloris/connection saturation budget or published disk-pressure thresholds were tested.
2. Tests contain adversarial malformed/chunked requests but are **not an independent live penetration test**, real bandwidth saturation trial, or real video browser upload inspection. System resource utilisation was not measured on a production-size sample.
3. A local test used deliberate timeout and temp-file cleanup, but no live container crash/recovery experiment involving a partially spooled customer video was executed. No schema migration occurred.
4. The existing **two moderate Vitest dev-tool advisories** (D-321) are still open; passing a high-severity npm audit gate does not mean the entire npm tree has zero advisories.
5. The local test suite and disposable PostgreSQL run are release gates **only for code**, not proof of hosted durability of the temporary video data (media storage S-06.03.06 remains separate).
6. Rollback: restore the prior app version but that would reopen pre-parser resource exhaustion. A safe operational fallback is to restrict video uploads upstream while applying a corrected guard. Temporary spools do not carry durable records; code change requires no schema rollback.
7. Full-history `uv run python scripts/verify_board.py` was not verified by this Render Docker build (shallow checkout history); 67 unit tests verify the verifier but do not certify the board.

`main`, customer/production services, provider credentials and databases remained untouched.
