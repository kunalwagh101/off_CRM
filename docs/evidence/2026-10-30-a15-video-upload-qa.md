# A15 bounded video uploads — executed Render QA (2026-10-30)

## Revision and deployment

- Repo/branch: `kunalwagh101/off_CRM/develop`.
- **Actual application and frontend revision tested:** `0c28d7c9be64d24a67f846142c5ff1dd56f50af3`, containing new A15 upload handler/tests and Vite 8.1.6 lockfile patch.
- QA isolated Render runner: `off-crm-review-runner-20261015`, service `srv-db86p4u89jmc73cehns0`, deploy **`dep-dbhqd96i0phs73f1vfrg`**.
- Dockerfile: `Dockerfile.review`, using SQLite fixtures and disposable PostgreSQL cluster. This is **not** a customer production deployment.

## Test evidence (actual Render build output, 2026-10-29 UTC)

| Gate | Observed result |
|---|---|
| `npm ci` Vite 8.1.6 and lockfile | **PASS** (installed 57 packages) |
| React/Vitest `npm test` | **212 passed** in 18 files |
| Frontend `npm run build` | **PASS**; backend stage consumed its output |
| `npm audit --omit=dev --audit-level=low` | **0 production dependency vulnerabilities** |
| `npm audit --audit-level=high` | **PASS** at high severity; **2 moderate vulnerabilities remain** in `@vitest/mocker <=4.1.11`, inherited from pinned `vitest@4.1.11` |
| `uv run ruff check --select E9,F63,F7,F82 .` | **All checks passed** |
| Contact import/export regression group | **19 passed, 1 warning** |
| Workspace-context security cases | **3 passed, 1 warning** |
| CRM deterministic cursor-lock test | **1 passed** |
| 12 repetitions of concurrent API creation/restart test | **12/12 passed** |
| CI/board verifier test files | **67 passed** |
| **Full Python suite, SQLite mode** `uv run pytest -q` | **2766 passed, 45 skipped, 44 warnings** in 260.52s |
| Desktop/mobile Chromium Contacts workflow | **PASS 1280px / PASS 390px**, 503 contacts, 6 pages, last contact, search and controls |
| PostgreSQL revocation named case | **1 passed, 1 warning** |
| PostgreSQL hosted/storage focused suites | **215 passed, 1 warning** |
| **Full Python suite, disposable PostgreSQL** `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` | **2786 passed, 94 skipped, 44 warnings** in 320.22s |

The six newly added `tests/test_video_upload_security.py` tests are included in **both** full-suite runs. The full-suite totals rose by exactly six from the prior 2760/2780 baseline. Test cases cover both video-media/render HTTP entry points, oversized payloads and bounded `UploadFile.read(2049)`, repeat requests, empty uploads, authentication, forged small Content-Length and valid WebM import. The isolated minimal FastAPI RED reproduction mentioned in the work order is **not** equivalent to an off_CRM baseline RED test. These are authenticated API adversarial checks, **not a comprehensive external penetration test**.

## Security audit and remaining work

- **D-319/A15 is PARTIALLY mitigated, still OPEN.** Endpoint reads are bounded by `OFFSETX_MAX_UPLOAD_BYTES + 1`; a large multipart body can still be parsed/spooled by Starlette **before** the endpoint runs. Aggregate upload concurrency and disk quotas, interrupted stream cleanup and video-specific size policies need separate streaming tests and operational evidence. No claim of production DDoS protection.
- **D-320:** Vite 8.1.4 triggered 3 npm advisories including 1 high; patched to Vite 8.1.6. Clean `npm ci` and the high-severity audit gate now PASS.
- **D-321:** two moderate development-tool-only advisories remain in Vitest's mocker (`GHSA-qxg6-89mg-rqv8`, `GHSA-xp26-3454-mjgp`). Package's offered patch `vitest@4.1.12` is outside the pinned version. Resolve with locked dependency upgrade and run npm audit, frontend tests, production build and Render checks. Do **not** disable the audit or assert 0 vulnerabilities across the entire tree.
- Existing skips and deprecation warnings remain recorded, not hidden. Browser acceptance covers Contacts flows, **not video upload using a real browser or a load-attack harness**. Full-history `uv run python scripts/verify_board.py` still not run because review Docker checkout lacks full Git history; 67 verifier test cases do not certify a board verification run.
- **S-06.02.50 IN_REVIEW**, **S-06.02.23 IN_PROGRESS**; other board states unchanged. No customer data, production service, provider sending, schema migration, `main` branch or production secrets touched.
- No rollback execution needed (no schema changes), but reversing this handler patch reopens the A15 memory issue; do not revert without a different tested byte cap. No production rollout has been authorized.

**Render final status at first handoff draft:** test-backed image stages completed, exported image pushed, registry cache export pending. If status later becomes `live`, append an explicit separately verified update; do not infer LIVE from the image build pass.
