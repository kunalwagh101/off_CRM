## 2026-11-04 — A32 restricted sandbox work directory (test-first isolated review)

- S-06.02.64 / F-06.02: corrected a high-priority audit bug in `SandboxWorkspace.prepare()`: host-owned 0755 work directories could not be written by the container's UID/GID 65534. Keep per-job root 0700, inbox 0755 (mounted read-only), and only /work sticky-writable 01777 (mounted rw). Refuse symlinked directories, and use no-follow file-descriptor-based fchmod to avoid changing a redirected target. Docker user, capabilities, egress, storage and network controls are unchanged.
- **TDD RED**: test-only 64af3c5 / Render dep-dblipuff3r2c73a96th0: all five new A32 tests failed as expected. **Focused GREEN**: corrected executable source c63fe5c / Render dep-dbliqluc6qcc73bht1hg: all five passed (43 deselected), including a real Linux UID 65534 subprocess writing through a directory descriptor; not an actual Docker execution.
- **Observed broader gates on exact executable source**: full SQLite 3,002 PASS/56 skipped/44 warnings; focused PostgreSQL 215 PASS; 12/12 repeated concurrency checks; real Chromium desktop/mobile Contacts and Public Demo, A09 and A18 Chromium, front-end build and security/static and structural board checks PASS. Full disposable PostgreSQL and Render LIVE state are still pending; do not claim those as finished. Docker-review structural verifier used `--skip-tests` and did not replay Git evidence history.
- Remaining release gates: real Docker sandbox output integration on native Linux with pinned image, independent penetration, full-history verifier, error-reference/failure log acceptance and production owner signoff. S-06.02.23 audit remains IN_PROGRESS; S-06.02.64 stays IN_REVIEW. No main/customer service deploy or data changes. Details: `docs/work-orders/S-06.02.64-sandbox-writable-workspace.md` and `docs/evidence/2026-11-04-a32-sandbox-workspace.md`.

## 2026-11-04 — A20 private media works with API-token authentication (isolated review)

- S-06.02.63 / F-06.02: selected the A20 media auth defect after checking the current develop board and open audit. The active S-06.02.23 audit remains separate and IN_PROGRESS.
- **TDD RED:** test-first `b4b2833` / isolated review `dep-dblhbtu417fc738i5b5g`: 8 expected A20 failures, one cookie-mode test already passed. **Early GREEN regression:** faulty regex blocked module parsing in `fdfee395` / `dep-dblhe1lg1s2s73ensrm0`; fixed source `af434cfbc8c50bd7ba6a7c937595347b15b1761d`, isolated review `dep-dblhej942hec73889ntg`.
- Shared `fetchMedia` now attaches bearer tokens only on same-origin API paths; cookie-only mode stays supported. Audio/footage/stills use authenticated binary requests; 401/403 are not silently treated as 404. Image review and video thumbnails create short-lived, size-bounded object URLs and revoke them on cleanup. No token appears in an image/video URL.
- **Observed GREEN on exact executable source:** frontend 223 tests passed (including all 9 new), production TS/Vite build PASS, npm production audit 0 advisories; full SQLite 2,997 PASS/56 skipped/44 warnings; full disposable PostgreSQL 3,021 PASS/101 skipped/44 warnings and focused PostgreSQL 215 PASS, backend auth stage 35 PASS; desktop and mobile Chromium Contacts and Public Demo browser checks PASS. Docker structural board verifier passed with full-history replay disabled. Two moderate development-only npm advisories remain.
- **Isolated review deployment is LIVE:** dep-dblhej942hec73889ntg at 2026-11-04T11:51:12.004417Z on exact code af434cf. Full Docker review gates passed, including real disposable PostgreSQL and desktop/mobile Chromium. Real token-only image/video browser acceptance, independent penetration and customer rollout are not performed, and structural board verifier --skip-tests is not a historical evidence replay. No main or customer deployment; S-06.02.63 IN_REVIEW. Work order and detailed evidence: `docs/work-orders/S-06.02.63-token-media-auth.md` and `docs/evidence/2026-11-04-a20-token-auth-media.md`.

## 2026-11-04 — A14 isolated Render QA LIVE, exact source

- `dep-dblg7k8u01pc73a4m7lg` reached **LIVE** at **2026-11-04T10:27:18.435081Z** on tested source `1c1d3a2b1e0acf1262776b5c082adacce691d776`. Last executable change is `2e709a5`. Render logs explicitly confirmed the QA marker service was live.
- Source-bound focused A14 12 passed/1 early-stage PG skipped; SQLite 2,996 passed/56 skipped; real PostgreSQL 3,020 passed/101 skipped, focused PostgreSQL 215 passed; Chromium desktop/mobile and configured frontend/security gates passed.
- Isolated test doubles and disposable DB do **not** prove actual customer email delivery or constitute independent penetration testing. The full-history verifier, external provider acceptance, supervised rollout and audit remain open. No `main` or customer service deployment; S-06.02.62 stays BACKLOG.

## 2026-11-04 — A14 exact-source isolated Render regression acceptance

- Source **`1c1d3a2b1e0acf1262776b5c082adacce691d776`**, whose last executable/test change is `2e709a59479d374397d66abf242f9e4148d6c879`. The isolated review runner **`dep-dblg7k8u01pc73a4m7lg`** executed the current files, including the actual OS-process crash and adversarial race tests.
- TDD RED initial five expected FAIL at `ac10fa0` / Render `dep-dblfslqjnfac73ft665g`. First GREEN five passed at `19682d5`. Final A14 targeted gate **12 passed, 1 skipped** (the PostgreSQL-only test is enabled in the full PG stage).
- Full SQLite regression **2,996 passed, 56 skipped, 44 warnings**. Full disposable PostgreSQL regression **3,020 passed, 101 skipped, 44 warnings**, including PG two-live-app idempotency race. Focused PostgreSQL **215 passed**; frontend tests/build, npm security audit, Chromium desktop and mobile, Ruff, security and structural board verifier gates passed.
- Docker review image built/exported successfully; final Render service LIVE status had not yet been observed when this checkpoint was recorded. Structural board verifier ran `--skip-tests` with zero full-history evidence command executions. This is **automated QA**, not independent penetration, a real provider send, customer production deployment, or proof the audit is complete.
- S-06.02.62 stays BACKLOG while S-06.02.23 production audit remains IN_PROGRESS and production acceptance is incomplete. No `main` or customer service changes. Evidence: `docs/evidence/2026-11-04-a14-atomic-http-idempotency.md`.

## 2026-11-04 — A14 final-source extended adversarial and crash tests (QA pending)

- After the first GREEN, `6dd3618` added an attacker racing a victim's key with changed payload and a SQL-metacharacter key; `2e709a5` added a true OS-process `os._exit(47)` after CRM insertion and before the enclosing idempotency transaction commits. After a restart, the campaign and key must both be absent, and exactly one retry may succeed. These are synthetic tests on disposable local data, not a customer server.
- `0b66f15` added replay after provider construction fails; the code fix `c6d1192` moves provider creation into the external operation callback so a known completed replay does not re-contact the provider.
- Exact final executable/test source: `2e709a59479d374397d66abf242f9e4148d6c879`. Full real PostgreSQL, SQLite, frontend, Chromium, security gates and final Render LIVE status are **not yet observed on that source**. An earlier review runner `dep-dblg1uc9v7es739u8t10` ran code only through `38371c`, so its results cannot certify these later changes.
- No customer or `main` deployment. S-06.02.62 remains BACKLOG under active S-06.02.23 audit and external acceptance gates.

## 2026-11-04 — A14 follow-up: completed sends must replay even without provider setup

- A completed send's replay still constructed the mail provider first; rotated credentials or unavailable adapter setup could fail before a valid saved response was read. Added `tests/test_api_idempotency_a14.py::test_A14_completed_send_replays_even_if_provider_setup_is_now_unavailable` test at 0b66f15.
- Moved the `_mail_provider` call inside the external `operation()` at code c6d1192. This leaves the durable pre-send claim around adapter setup, but skips adapter construction for a completed replay. Keeps all earlier A14 requirements and does not send a real email.
- Full Render QA on final source is **not yet observed** at this checkpoint; do not treat earlier isolated QA code 19682d5 or 38371c as passing this later change. No customer/main deployment.

## 2026-11-04 — A14 atomic HTTP idempotency (test-first build-ahead, final QA pending)

- On develop, the original helper looked up a key, performed the side effect, then saved the result. **TDD RED** at test-only `ac10fa0` / isolated Render `dep-dblfslqjnfac73ft665g`: **5 expected FAIL**, including two actual API app instances racing, payload/key conflicts, crash-after-mutation, replay after uncertain send and malformed headers.
- **First GREEN** app source `19682d5` / isolated Render `dep-dblfu1ugekts738a7780`: the same five A14 tests **PASS**. CRM-only keyed effects and saved responses commit in one `OutreachStore.transaction(immediate=True)` across SQLite processes and PostgreSQL connections. Provider and email actions save a durable in-progress key **before** transport; an ambiguous outcome blocks same-key resend. Completed responses replay unchanged.
- Every keyed route now hashes caller and canonical Pydantic request fields; conflicting caller/payload reuse returns 409 and invalid/unverified legacy keys refuse rather than leak. Old tests updated to use identical replay and assert changed-payload conflict. Additional real-PG, authenticated caller, legacy record and completed external-replay tests are in `tests/test_api_idempotency_a14.py`, source `7c47b34`; full exact-source QA still pending.
- **Release restrictions:** live SES/provider exactly-once delivery is not proven by synthetic calls; unresolved external keys need reconciliation. Full-history board verification, production auth/tenant acceptance and independent penetration remain open. Audit S-06.02.23 stays IN_PROGRESS and S-06.02.62 stays BACKLOG; no customer/main deployment. See `docs/evidence/2026-11-04-a14-atomic-http-idempotency.md`.

## 2026-11-04 — A11 QA runner deployed LIVE, exact-source verification

- Render deployed the isolated review runner `dep-dblffhijnfac73fs3770` **LIVE** at 2026-11-04T09:35:47.896966Z on executable source `8957a27b9d1d7d646757bf86d51f8059b21a0781`. Render logs also confirmed "Your service is live" at 09:35:48 UTC.
- Isolated tests passed: A11 targeted 14/14 (PG-only 1 skipped at early stage), SQLite 2,984/2,984 executed, real PostgreSQL 3,008/3,008 executed including PG multi-worker A11, focused PG 215/215, real Chromium desktop/mobile, configured frontend/security gates. Source did not change during documentation updates.
- This is a QA runner, **not** paid-provider/customer production deployment. Independent third-party penetration, live provider billing/receipts and full-history verifier are still not accepted. Story remains BACKLOG under active audit; no `main` push.

## 2026-11-04 — A11 full isolated Render QA evidence (source 8957a27)

- Exact **executable source**: `8957a27b9d1d7d646757bf86d51f8059b21a0781`, review service `srv-db86p4u89jmc73cehns0`, deploy `dep-dblffhijnfac73fs3770`.
- RED source `b57c971` (8 expected failures) and separate key-rotation RED `e488c30` (1 expected failure), observed via failed isolated Render builds.
- GREEN focused A11 gate: **14 passed, 1 skipped** because no PG URL in early build stage. Full SQLite **2,984 passed, 55 skipped, 44 warnings**. Full disposable PostgreSQL (environment sets `OFF_CRM_TEST_POSTGRES_URL`): **3,008 passed, 100 skipped, 44 warnings**; includes the A11 spawned independent-worker PostgreSQL contention test. Focused PostgreSQL regression: **215 passed**.
- Browser: Chromium Contacts, and Public Demo, both desktop and mobile PASS. Configured frontend checks, egress wall, security, static checks, concurrency and structural board verifier completed; board verifier `--skip-tests` ran **zero** historical evidence commands and cannot substitute for full-history replay. All configured Docker review build stages succeeded and the image was exported; final deployment LIVE status was still pending when recorded.
- External penetration test, paid-provider invoice/receipt validation, supervised production service and full-history evidence replay are **not performed/certified**; keep story BACKLOG and never promote `main` automatically. `docs/evidence/2026-11-04-a11-ai-quota-reservations.md` provides rollback details.

## 2026-11-04 — A11 dual-scope AI quota reservation (TDD and QA under review)

- **RED:** b57c971 / isolated Render dep-dblf71ugekts7388c3g0: 8 expected A11 failures. Two independent broker workers both reached a fake provider despite a one-call daily or minute cap (local and hosted SQLite); corrupt counters were accepted and no durable reservation API existed. **Second RED:** e488c30 / dep-dblfdv8u01pc73a2of90: key rotation bypassed the same workspace's daily call limit (1 expected failure).
- **Implementation source:** 8957a27 (quota.py and broker.py) after iteration 97191af, 59f29dc, 4abe3d9 and 1cc7dac. Before chat, image or transcript transport, the single broker books one ticket in both the physical account and workspace quota ledgers under the same existing PostgreSQL advisory transaction or cross-process local OS lock. The generated ticket and conservative USD hold persist before network I/O; actual usage reconciles once. Invalid local/hosted counters refuse transport with secret-safe error reference; a crash leaves its attempt and reserved dollars held. Key rotation no longer resets a workspace budget. A missing/undocumented token price with a USD cap refuses rather than inventing free usage.
- **Initial GREEN, same source:** Render dep-dblffhijnfac73fs3770, A11 focused 14 PASS / 1 PG SKIP (the PG-only race test is activated in disposable PostgreSQL stage). Other configured Render gates still running at this checkpoint. Do not say full regression or deployment LIVE until observed.
- **Safety boundaries:** No real paid provider, unreviewed external API, production database, customer service or `main` changed. PostgreSQL release gate and independent security acceptance remain open; preserve work in BACKLOG under active S-06.02.23 audit. `docs/evidence/2026-11-04-a11-ai-quota-reservations.md`.

## 2026-11-04 — A16 exact-source isolated Render QA completed LIVE

- RED `61cc4fa` / `dep-dbldu5bncjis73djca20`: 5 expected failures at `EmailDeliveryService.work_once`, proving provider factory exceptions were unhandled after job claim. GREEN source `144e1cb` / isolated Render `dep-dbldur942hec73fvgeq0` **LIVE at 07:52:04 UTC**.
- Green QA: A16 focused **5 PASS / 16 deselected**; full SQLite **2,970 PASS / 54 skipped / 44 warnings**; full disposable PostgreSQL **2,993 PASS / 100 skipped / 44 warnings**; focused real PG **215 PASS**; verifier unit **67 PASS**; concurrency repeated **12/12 PASS**; frontend build/tests/npm audit, Ruff and real desktop/mobile Chromium gates PASS. Structural board verifier `--skip-tests` PASS (0 evidence commands replayed; source was 144e1cb).
- Pre-send failures settle as failed or bounded retry_wait with one secret-safe reference; unknown post-send outcomes remain quarantined. No production/main or customer SES traffic. Actual worker deployment S-06.02.40, ongoing audit S-06.02.23, independent penetration, real provider acceptance and full-history verifier block DONE. Source+test commit is 144e1cb; following documentation commits do not change executable code. See `docs/evidence/2026-11-04-a16-email-provider-setup.md`.

## 2026-11-04 — A16 email-provider factory remediation (TDD, isolated QA ongoing)

- Scope: `S-06.02.61 / D-363 / A16`. Test-first `61cc4fa` on isolated Render `dep-dbldu5bncjis73djca20` **failed 5/5** expected cases at the real `EmailDeliveryService.work_once` entry point. Old provider constructor exception escaped before send and left the claimed job unhandled.
- GREEN source `144e1cb` on isolated Render `dep-dbldur942hec73fvgeq0`: focused A16 **5 passed** (permanent and unknown setup failures, transient retry and restart, five-attempt limit, unrelated job continuity). Code keeps pre-send exceptions separate from post-send delivery-unknown quarantine, returning one secret-safe failure reference. Existing schema and credentials unchanged.
- Broader SQLite, real PostgreSQL, browser/frontend and board gates were still running at this checkpoint. Story remains BACKLOG under active S-06.02.23 audit and actual worker deployment dependency S-06.02.40. No customer/SES traffic or main deployment. Full evidence: `docs/evidence/2026-11-04-a16-email-provider-setup.md`.

## 2026-11-03 — A12/A13 exact-source isolated Render QA LIVE

- Test-first A12/A13 repairs from earlier commits now have full isolated QA on exact code/test source `6528060`: new persisted-cache restart regression 9 PASS, broker A13 2 PASS, full SQLite 2965 PASS/54 skipped, real PostgreSQL 2988 PASS/100 skipped, focused PG 215 PASS, browser/frontend/security and board structural gates PASS. Render deploy `dep-dbl0abqjnfac73a521g0` LIVE at 16:19:15 UTC.
- Both stories remain IN_REVIEW until independent penetration, real-provider/customer acceptance and full-history board verification. No production/main deployment. See `docs/evidence/2026-11-03-a12-a13-cache-review.md`.

## 2026-11-03 — A16 provider setup failure remains open

- Source audit found \`EmailDeliveryService._send_job\` still acquires provider before its send exception boundary. Logged D-363 and BACKLOG story S-06.02.61 with failure-injection, restart and no-double-send test-first acceptance. No runtime code or live mail changed; source evidence only.

## 2026-11-03 — A11 quota race filed for atomic repair

- Current-source audit confirmed the separate pre-call quota check and post-call record still cannot reserve a budget across processes. Corrupt local usage can reset. Logged D-362 and S-06.02.60 in BACKLOG with a red-first real-process/PostgreSQL work order. No application code was modified and no new penetration result is claimed.

## 2026-11-03 — A12/A13 AI response-cache correctness and model provenance (IN_REVIEW)

- Started two traceable F-06.02 remediation stories: S-06.02.58 / D-360 (changed factual evidence reusing an old near-match answer) and S-06.02.59 / D-361 (one model's output shown as another model's cached result). Each has a work order, testable acceptance and the original audit finding retained.
- Real test-first Render RED: exact source 3e06faa / dep-dbkrmik9v7es73f6gj1g **4 failed**: incorrect 42 -> 420 million and negated-approval near hits, plus missing `model_id` and `system_prompt` cache API contracts.
- Source fix: factual results require exact canonical payload equality; cache partition now includes model ID, SHA-256 digest of system instructions, SHA-256 digest of request options and output format, plus the existing privacy/workspace boundaries. The broker passes the contract on both reads/writes. No raw system prompt is stored in indexed keys. No table migration or extra dependency.
- Initial isolated GREEN on source 25f882c / dep-dbkrodt9fdbs73c5vik0: four focused A12/A13 tests passed. Legacy fuzzy-cache expectations were updated to the stronger exact-fact contract, not silently skipped. Added two end-to-end `EgressBroker.call` regressions for different prompts/models and an early Render gate; exact-source full regression remains pending.
- Both stories stay **IN_REVIEW**. Independent penetration, real provider/customer acceptance, complete historical board verifier and production deployment remain open. No `main`, paid-model, customer data or live email changes.

## 2026-11-03 — A09 Enter approval bypass: exact-code isolated QA LIVE, IN_REVIEW

- TDD RED dfe6b78 / Render dep-dbkpkiek1f9s73dllh50: 4 failed by dispatching unapproved Enter. Original first GREEN 0fef11d later exposed five unsafe legacy tests (D-359): 5 failed / 2949 passed SQLite. Corrected tests and explicit model self-approval rejection at 065c310.
- Final Render dep-dbkps0m7bikc73fil3vg on source 065c310 **LIVE at 08:59:44 UTC**: A09 focused 4 PASS, legacy Enter 34 PASS, real Chrome A09 4 PASS; full SQLite 2954 PASS/54 skip, real PostgreSQL 2977 PASS/100 skip, focused PG 215 PASS, repeated concurrency 12/12, desktop/mobile browser, frontend/build/audits, Ruff and structural verifier PASS.
- S-06.02.57 moved IN_REVIEW. A09 historical finding closed only for tested Enter custom-JS submission; independent live penetration, effect-bound approval after DOM change, full-history verifier and customer production deployment remain open. No main/customer change. Evidence docs/evidence/2026-11-03-a09-enter-approval.md.

## 2026-11-03 — A09 keyboard approval escape: TDD RED, guarded fix awaiting QA

- Selected S-06.02.57 with owner build-ahead instruction, existing audit S-06.02.23 still in progress. Test-only develop dfe6b78 was genuinely RED on isolated Render dep-dbkpkiek1f9s73dllh50: 4 A09 cases failed because unapproved Enter reached CDP key dispatch.
- Existing `Page.press` now treats unknown/non-English Enter focus as potentially consequential, through the same human approval gate. The model cannot self-confirm; benign keyboard controls still use the existing path. D-358 and DD-137 record defect and false-positive cost.
- Final targeted/full SQLite/PostgreSQL/Chromium acceptance is **pending** on this revision; no independent live penetration or customer/main deployment. Do not mark A09 closed or S-06.02.57 DONE.

## 2026-11-03 — A21 isolated Render QA activated

- Review deploy dep-dbkp0b7b9u1s738244k0 completed LIVE at 08:04:59 UTC on exact source e45469a. This certifies the QA runner stage, not customer or main rollout. A21 stays IN_REVIEW with independent pen, full-history board and real-provider acceptance pending.

## 2026-11-03 — A21 full decoding reviewed on isolated Render

- Corrected e45469a tested in dep-dbkp0b7b9u1s738244k0: 10 A21 PASS, 113 image/video PASS, SQLite 2950 PASS, PostgreSQL 2973 PASS, focused PG 215 PASS, verifier 67 PASS, concurrency 12/12 PASS, frontend/build/audits and Chromium desktop/mobile PASS.
- Full pixel checks remain in generated-image approval; lightweight video media classification preserved. S-06.02.56 moved IN_REVIEW, not DONE: independent penetration, resource stress, full-history verifier and real provider/customer acceptance outstanding. No main/customer deployment. See docs/evidence/2026-11-03-corrupt-images-a21.md.

## 2026-11-03 — A21 correct shared video-media probing regression

- First full isolated SQLite suite on `db02e52` failed 3/2946 pass/50 skip because header-only video classification was unintentionally changed, and the blank placeholder fixture became a larger valid image. Logged D-357.
- Corrected `e45469a`: preserve video `image_size` header inspection, add private full-decoding gate for generated-image approval and use a genuinely small valid blank PNG in the byte-threshold test. No relaxation of corrupt-image rejection.
- New Render `dep-dbkp0b7b9u1s738244k0` focused **10 A21** and **113 image/video** PASS. Full SQLite/Postgres/Chromium gates ongoing; no main/customer release. Evidence docs/evidence/2026-11-03-corrupt-images-a21.md.

## 2026-11-03 — A21 generated image validation (final Render QA pending)

- Source `7748855` adds full bounded decoding of PNG/JPEG/GIF/WebP and strict MIME agreement before image review; invalid input is recorded without aborting the batch. Pillow 12.3.0 promoted to direct dependency from already-present lock.
- TDD RED 2 failed / 2 passed on Render `dep-dbkolbnb9u1s73819ns0` and early GREEN 7 passed on `dep-dbkonpnb9u1s7381fptg`. False-positive binary fixtures D-356 corrected and additional security tests committed `db02e52`. Final review `dep-dbkopnp5efls73f7u9j0` pending.
- Independent penetration, memory peak, full-history board verification and customer/main release not claimed. Evidence docs/evidence/2026-11-03-corrupt-images-a21.md.

# Changelog

## 2026-11-03 — A18 numeric evidence isolation QA passed (IN_REVIEW)

- Final Render review dep-dbkni7fb9u1s73fubjl0 at exact source c1eefe2 LIVE. TDD RED previously 15 fail/13 pass; corrected source A18 48 PASS/2 skipped, real Chromium A18 2 PASS, full SQLite 2940 PASS, full PostgreSQL 2963 PASS, focused PG 215 PASS, verifier unit 67 PASS, concurrency 12/12 PASS, frontend and browser gates PASS.
- Moved S-06.02.55 to IN_REVIEW and updated A18 audit as closed for verified numeric cases. No independent penetration or full-history board replay yet; no main/customer release. See docs/evidence/2026-11-03-numeric-claim-integrity.md.

## 2026-11-03 — F-11.02 numerical evidence verification repair (S-06.02.55, QA pending)

- Real Render TDD RED `dep-dbkn8p59fdbs73bquspg` at test-only source `00b1657`: **15 failed / 13 passed / 8 deselected** in the targeted numeric-claim suite. No production data or model calls.
- Source-bound numeric matching now checks sign, decimal/thousand continuations, units immediately attached or marked with percent, currency prefixes, and spaced sign/percent. Ordinary sentence punctuation and existing nonnumeric claim behaviour remain covered by integration tests. Recorded DD-134 design/limitations. Added Unicode sign/decimal/grouping/percent and space-grouped thousands regression cases, plus a real Chromium browser-capture acceptance step and structural board check in the isolated Render image. Exact final gate still pending.
- Full Render QA and board verifier not yet observed. No main/customer rollout. F-11.02 original four sub-stories remain DONE; A18 repair stays IN_PROGRESS pending evidence.

## 2026-11-03 — Production-audit A18/A21 triage (S-06.02.23, IN_PROGRESS)

- Source-rechecked the current numeric-claim verifier and generated-image gate on `develop`. A18 remains open as D-354 / S-06.02.55 (signed/decimal/grouped figures falsely matching a short claimed number). A21 remains open as D-355 / S-06.02.56 (header-only image accepted and truncated GIF raising uncaught `struct.error`).
- Updated the September audit index, defect log, backlog, board and work orders. **No application change, passing regression, independent penetration or Render deployment is claimed** for these two findings. The audit still has other unchecked rows.

## 2026-11-02 — F-06.22 independent QA completion (IN_REVIEW)

- Final implementation/test source `f6de8a1`, isolated Render review `dep-dbk9o0gn74is73brdodg` **LIVE at 2026-11-02T14:37:46Z**. Seven targeted tests PASS; full SQLite **2,892 passed/48 skipped**, full disposable PostgreSQL **2,915 passed/94 skipped**; focused PG **215 passed**, verifier unit **67 passed**, 12/12 concurrency and Chromium desktop/mobile PASS. Frontend tests/build/audits and Ruff passed as Docker build gates.
- D-351/352 imported-email whitespace and oversized-pagination fixes verified. D-353 test harness corrected to read textual EXPLAIN columns. SQLite 5,004-row synthetic query measured 11.4ms but the query performs a table scan; PostgreSQL 5,004-row test executed with planner assertion, execution time not separately recorded.
- Release **IN_REVIEW**: Q-27 shared-vs-isolated CRM, independent live penetration test, full-history board verifier and larger production-scale query-plan proof remain open. No customer/main deployment or data migration.


## 2026-11-02 — F-06.22 security and imported-contact corrections

- Render TDD RED `dep-dbk9k6ijnfac73a0jpjg` on `a1c68e1`: 2 failed, 4 passed. Found D-351 (TAB/CR/LF values missed by contact duplicate search) and D-352 (unbounded OFFSET).
- Committed fix `d931ba8` to `develop`: one SQL email-normalisation expression across search/group/preview, plus `offset <= 1,000,000` at API and service boundaries. Added 5,004-record performance/query-plan regression on SQLite and real PostgreSQL. No schema change or contact mutation. Full Render QA outcome must be recorded separately.


## 2026-11-02 — Backend duplicate-contact review (F-06.22, IN_REVIEW)

- Added authenticated, read-only `GET /api/v1/crm/duplicates`: case- and outer-whitespace-normalized email groups, full group totals, safe search, bounded pagination and three-record previews. No migration or automatic merge.
- Four TDD tests observed RED on Render `e86ff75` (4 failed as feature missing), then GREEN on `a0e9daf` (4 passed), including auth and SQL-shaped input cases. Isolated Render QA `dep-dbk9797f3r2c73932q0g` LIVE on `a0e9daf`: SQLite 2,889 passed, PostgreSQL 2,912 passed, focused PG 215 passed, verifier unit 67 passed, concurrency 12/12, Chromium desktop/mobile and frontend tests/build/audits passed. No production deploy or completed independent penetration.
- Release stays in review for Q-27 CRM tenancy, scale/PG and additional QA evidence.

## 2026-11-02 — AI history migration: isolated Render QA passed

- Reviewed on `develop` implementation source `1236104` in isolated
  Render `dep-dbk8on7f3r2c7391pn50` (LIVE). New migration tests:
  12 PASS / 1 PostgreSQL-only skip at SQLite gate, the PG import case
  later PASS; full SQLite **2,885 PASS** and full PostgreSQL **2,908 PASS**.
  Focused PostgreSQL 215 PASS, Chromium desktop/mobile PASS, verifier unit
  67 PASS and concurrency 12/12 PASS. No customer/main deployment.
- AI context import/skip is operator-only with a protected source backup.
  The entire F-06.03 and S-06.03.06 remain open for other stores and
  external backup/restore proof.


## 2026-11-02 — AI-context import QA

- 2026-11-02: isolated Render review `dep-dbk8on7f3r2c7391pn50` on source `12361049103a8913753899b34eba5ef2f18698e6` finished LIVE at 2026-11-02T13:30:28Z. Full PostgreSQL 2,908 passed, 94 skipped, 44 warnings. Docker review completion requires SQLite, frontend, Chromium, PostgreSQL and focused early stages. No customer deployment. Full-history board verification, independent penetration and external backup restore not evidenced; S-06.03.06 stays BACKLOG.


## 2026-11-02 — AI context history migration (S-06.03.06 partial)

- Added `offsetx-db import-context --yes|--skip`: owner-controlled import or deliberate skip of old local AI task context. Uses a private SQLite online archive, rejects conflicting hosted records, preserves workspace and template counts, and imports both context tables in one database transaction.
- Tests added for imported task decisions and counters, workspace isolation, WAL-aware backup, archive permission/restore, interrupted cleanup, destination rollback, exclusive workspace locks, missing/corrupt source, CLI approval and real PostgreSQL re-open.
- TDD RED `ffd81e0` failed test collection as the module did not exist; initial GREEN `2adfdcc` six focused tests passed. Hardened code through `1236104`, reviewed in isolated Render `dep-dbk8on7f3r2c7391pn50`: 12 targeted tests passed, 1 PostgreSQL-only test skipped at the SQLite stage; full QA status recorded separately in BUILD_STATE.
- The wider F-06.03 storage story, live customer import, external backup/restore, and independent security review remain open. No main or customer deployment.


## 2026-11-02 — Correct PostgreSQL AI template counter UPSERT

- First hosted context review detected two separate failures the focused SQLite tests missed: health check used an old local file (D-348, corrected in `7fdc4f2`), and PostgreSQL rejected ambiguous counter UPSERT columns (D-349, corrected in `1ff58da`). Added exact failing tests as early review gates, without hiding or weakening them. Full QA on the corrected PostgreSQL change remains open.


## 2026-11-02 — Fix hosted AI-context health readiness regression

- Full SQLite QA found 3 HTTP 503 failures: readiness still probed the former local `ai_context.db` instead of the active hosted context database. Fix `7fdc4f2` selects the real database target, adds API readiness assertions and tests those three exact regressions before the broad suite. Follow-up isolated Render is still in progress, not yet green at documentation time. Defect D-348 logged.


## 2026-11-02 — Hosted AI context and template statistics (S-06.03.06 partial)

- AI task progress, owner decisions, summaries and template performance are now backed by versioned tables in the explicitly configured hosted database. Old local installs still use their existing SQLite file. A hosted startup refuses to silently ignore an old `ai_context.db`, pending a reviewed migration command.
- TDD RED isolated Render 5 failed; first GREEN early test 5 PASS/one PG-only skip on `ce82d33`. The full SQLite/PostgreSQL/Chromium QA verdict is not yet claimed here. F-06.03 and story S-06.03.06 stay open.


## 2026-11-02 — Verified manual legacy timer cutover QA

- Isolated Render `dep-dbjri0utlv9c73e36570` reached LIVE on source `0232cf5e2d15493dd7538b10fcbc69e404609c47` after complete configured Docker QA: 14 targeted migration tests PASS (one PostgreSQL-only early-stage skip), 2,868 full SQLite PASS, 215 focused PostgreSQL PASS, 2,889 full PostgreSQL PASS, and Chromium desktop/mobile PASS. The CLI defaults imported automation to disabled and refuses concurrent/invalid/conflicting imports. No customer deployment or F-06.03 DONE claim.


## 2026-11-02 — Explicit legacy timer migration (S-06.03.06 partial)

- Added `offsetx-db import-timers --yes|--skip --data-dir PATH --archive-dir PATH` to copy legacy email/content timer settings safely into existing hosted documents or preserve hosted state. The tool archives original files before changing their names, refuses conflicts and symlinks, and keeps imported schedules and Gmail live-send consent disabled.
- Tests added for protected backups, conflicting hosted data, partial DB rollback, archive permissions, CLI confirmation, active workspace lock and crash-safe retry. First Render RED stopped at missing module; initial GREEN 9 focused tests passed on `3e9b87c`. Exclusive-lock follow-up `fe93aad` requires its own Render QA. No main/customer deploy, automatic sends or whole-feature DONE claim.


## 2026-11-02 — Hosted scheduler settings (S-06.03.06 partial)

- The isolated Render review `dep-dbjqubh42hec73dr2bu0` reached LIVE after all configured QA gates for source `6166be7`: hosted timer tests 6 PASS, SQLite 2854 PASS, focused PostgreSQL 215 PASS, full PostgreSQL 2874 PASS, Chromium desktop/mobile PASS and verifier-unit 67 PASS. This does not close the entire F-06.03 feature or the active production audit.


- Email and content scheduler configuration now use existing hosted database documents when `OFFSETX_DATABASE_URL` is configured. The unhosted file format is unchanged. An existing local settings file blocks silent cutover; database write errors do not create temporary fallback data.
- Added six TDD tests covering restart, old-file collision, database failure, local compatibility and real application storage classification. RED Render `dep-dbjqsn3bc2fs73dkcag0`: 6 failed (before implementation). First GREEN attempt `dep-dbjqtnjbc2fs73dkedjg`: 5 passed, 1 fixture key setup error; corrected test at `6166be7`. Latest Render `dep-dbjqubh42hec73dr2bu0`: 6 focused and 7 storage-readiness cases passed; broad QA still under way at this checkpoint.
- Remaining F-06.03 stories, independent security/recovery and owner-approved external backup/worker decisions are open; no main/customer deploy and no DONE claim.


## 2026-11-02 — A06 production-audit session-revocation regression

- Isolated Render review of the A06 session test completed the full Docker QA stages: 34 auth PASS, 19 export/contact PASS, 2848 full SQLite PASS, 2868 full PostgreSQL PASS, targeted PG 215 PASS, and both Chromium desktop/mobile suites PASS. Audit evidence now rechecks A06, A19 and A23. This is not a claim of full 35-finding audit closure, independent penetration or customer deployment.


- Added an API-level test that a logout revokes only its own session cookie, preventing cross-session logout or reuse of the revoked token. Render full review was started against exact test commit `37a6d2f`; no new QA pass or production release is claimed pending build completion. No runtime application change or migration.


## 2026-11-01 — Restore AI in the public demo

- Restore AI Chat, Compare, Plan and Image through the existing broker, with provider setup and AI-first navigation. Visitor AI keys/chats/logs are scoped to the verified login session. Keys are removed on logout; sample CRM writes remain protected.
- Fix foreign-workspace egress log detail exposure. Live vendor verification and original deployment backup/upgrade remain open; do not confuse tests with working external credentials.
- Deployed the repair on the existing visitor service at source 39084d3, 2026-11-01T00:31:55Z. Real HTTPS 37 checks and live AI/provider-setup browser flow passed. Final reviewed source 97e1e7b passed SQLite 2847, focused PostgreSQL 215, full PostgreSQL 2867, frontend 214/build and desktop/mobile Chromium; review service LIVE. Corrected two browser-harness locator/loading races. Updated the original service to 97e1e7b after the owner's go-ahead for the described temporary-data reset; LIVE 2026-11-01T00:55:24Z, existing Render credential settings retained. No main promotion. The existing Plan mode coordinates text work; this does not implement arbitrary CRM actions from chat.

## 2026-11-01 — Separate public visitor demo

- Add opt-in sample-only read-only visitor installation, public-demo workspace, visible login details and sample data. Private credentials are never advertised. Startup refuses existing private storage and shared database configuration; timers and connected-service actions stay disabled.
- Separate visitor demo is LIVE at https://off-crm-public-demo.onrender.com/ with verified login/read-only/logout and visible credentials. Render core checks: 2838 SQLite tests and desktop/mobile visitor Chromium passed. Evidence and remaining broader review: docs/evidence/2026-11-01-public-visitor-demo.md.
## 2026-10-31 — Owner browser-run cancellation (F-06.01)

- Added GET `/api/v1/ai/chats/{chat_id}/browser-runs` to view an owner chat's active run ID, and owner-only DELETE `/api/v1/ai/chats/{chat_id}/browser-runs/{run_id}` to request cancellation (HTTP 202). Foreign and stale run IDs cannot cancel other tasks. The existing POST now returns `cancelled` only after the running task's cancellation and cleanup; its workspace browser lease is always released.
- Browser tasks are tracked in a non-persistent registry, cancelled on chat deletion/shutdown/restore, and included in runtime close and storage inventory. No new AI egress or provider credentials. Cancelling a task is not the same as a monitored browser session.
- TDD RED `cf31c14` on Render `dep-dbiugrm7bikc73dtnrr0`: **3 failed / 40 passed**. Targeted GREEN `fd8a73a` on `dep-dbiuigg473hc73ambq30`: **44 passed**. Full SQLite **2828 PASS**, focused PostgreSQL **215 PASS**, full PostgreSQL **2848 PASS**, Chromium desktop/mobile **PASS**, verifier unit **67 PASS**; Render isolated review `dep-dbiuigg473hc73ambq30` **LIVE** on exact tested source `fd8a73ae4a13eb1e04aaf2f59a970050883df806`, finished **2026-10-31T13:29:26.28068Z**. No `main` or production deployment.
- IN_REVIEW, not production: real browser/provider cancellation, cross-process transport, watch-and-cancel UI, D-330, DNS/network firewall, upstream companions and independent penetration verification still pending.

## 2026-10-31 — Owner chat browser reading (F-06.01)

- Added owner-only, strictly typed and workspace-locked `POST /api/v1/ai/chats/{chat_id}/browser-runs`. A bounded goal and public URL reach the existing sandboxed AgentRun with the chat's temporary grants, strict live workspace policy and broker egress boundary. Read-only overlay denies click/type/press/select, and a 115-second wall / 90-second latency / $0.25 spend limit bounds a request.
- Security fix D-335: an HTTP request is not a watched browser session; always enforce the existing unattended domain rule. Render RED `dep-dbisj1ks728c7386u920` **1 failed / 36 passed**; corrected on `3150fbb`. Malformed URL/embedded credential rejection (D-336), owner scope, lease cleanup and executor preflight tests added.
- TDD RED `f92a3e5`, isolated Render `dep-dbisfo67bikc73dohamg`: **4 failed / 33 passed**. Targeted GREEN on latest `3150fbb`: **40 passed**. Final source `3150fbb` passed full SQLite **2824**, focused PostgreSQL **215**, full PostgreSQL **2844**, Chromium desktop/mobile, Ruff and verifier unit **67**; isolated Render `dep-dbiskimc6qcc739ivrcg` **LIVE**. No customer-facing attended run or production promotion.
- Remains IN_REVIEW: no live watch/cancel UI, no demonstrated real external provider/Docker browser session, owner-only read-oriented (not fully attended), DNS rebinding and production durability controls, D-330, upstream companions, independent pen and history verifier. No `main` or production deployment.

## 2026-10-31 — Authenticated chat tenant isolation and temporary browser approvals (F-06.01)

- Closed D-331: AI chat/project API calls now use the authenticated workspace, including lists, chat and project creation, message history, send, move, rename and delete. The AIChatService verifies ownership before storing messages or calling the AI responder, preventing foreign chat content from entering provider egress.
- Added D-332 backend owner workflow: typed `POST /api/v1/ai/chats/{id}/permissions` grants only an existing policy `ask` browser verb, `GET` reports active chat grants, owner `DELETE` closes them, and chat deletion also closes them. Approval is explicitly owner-only, bounded and memory-only, with expiry within one hour; a global or tool `deny` cannot be overridden.
- Runtime restore/shutdown revokes held grant objects. No new schema, long-lived token, external provider call or `main`/production deployment.
- Actual isolated Render TDD RED: `43a5d14` on `dep-dbiqkes9v7es738bb040`, **3 failed/26 passed**. First implementation review found two test-harness mistakes, corrected. Latest code `3588199` targeted agent/permissions **32 passed**, typed-body contract **1 passed**, hosted readiness **7 passed**, operational health **7 passed** on `dep-dbiqn77b9u1s73c8pp80`. Full suite/Chromium and LIVE QA still pending.
- Closed D-333: owner project deletion now returns 404 for a foreign/missing project instead of reporting success, with an authenticated cross-workspace regression. Final code `d2d4788`, Render review `dep-dbiqouvlk1mc73ffueb0` pending complete QA.\n- Full SQLite review of `d2d4788` found D-334: 2 failed/2815 passed, caused by the new transient registry being absent from app-state inventory and the runtime close order. Fixed on `8a35417` with `close()` lifecycle, `NOT_STORES` declaration and early QA gates for both tests; final Render review `dep-dbiqtah42hec73b8v1sg` pending.\n- **IN_REVIEW**, not customer-ready: the AI Copilot lacks the attended browser-agent execution and approval UI, D-330 and upstream S-04.01.01 remain open, and independent penetration/full-history verifier remain unverified.

## 2026-10-31 — Live agent-permission revocation (F-06.01 / D-327)

- Scheduled browser agents now reload workspace permission settings before **each** selected browser action. Owner changes to `deny` stop later actions in the same run; cached reads are covered.
- Security-sensitive workspace permission reads now reject corrupt settings and storage errors instead of silently returning an empty/default-allow policy. The authenticated permission GET/PUT API refuses damaged state rather than claiming an allow policy or overwriting it.
- A read failure produces a secret-safe operational error reference and a no-action refusal. Ordinary settings consumers keep their old lenient read behavior. No schema migration and no extra model/provider egress.
- Real Render TDD RED: `dep-dbifi0ui0phs739b7m80`, source `a45716a`, **2 failed / 22 passed**. GREEN candidate `12b9251`: **25 permission/agent tests passed**, typed-body API contract **1 passed**, operational health **7 passed** on review runner `dep-dbifjnrbc2fs73fbd6c0`. Full review stages are separate and must be confirmed before release.
- The first source `12b9251` passed full Render QA: **2809 SQLite tests, 2829 disposable PostgreSQL tests**, 215 focused PostgreSQL tests, and desktop/mobile Chromium; review deployment reached LIVE, not production.
- Follow-up D-328: an owner permission edit could preflight strict storage and then overwrite damage caused before its lenient write. Test-first Render RED **1 failed/25 passed** on `dep-dbifr0afngtc73dig9l0`. The corrected `save(..., strict=True)` checks the document **inside** the existing exclusive write lock. Targeted GREEN **26 passed** on corrected source `09ded49`; its final full QA remains a separate gate.
- Full SQLite on the first atomic-write source `09ded49` found D-329: **1 failed, 2809 passed** because ordinary settings writes passed `strict=False` into existing zero-keyword `_document()` test wrappers. Corrected on `e820071`: ordinary writes retain the original call interface; only permission writes pass `strict=True`. Targeted `26 passed`, concurrency `12/12 passed`, full SQLite `2810 passed`, focused PostgreSQL `215 passed`, full PostgreSQL `2830 passed`, desktop/mobile Chromium, Ruff, verifier unit `67 passed`. Isolated Render QA deployment `dep-dbifv8942hec73f36l50` **LIVE** on `e820071`. D-330 (missing settings interpreted as a fresh default-allow install) remains open; no independent penetration clearance.
- Still **IN_REVIEW**: attended chat permission-grant/close API, independent penetration and full-history verifier; upstream `S-04.01.01` remains IN_REVIEW. Not deployed to `main` or production.

## 2026-10-30 — Owner operational health for schedulers (F-06.02)
- New read-only install-owner API `GET /api/v1/operations/health`, separate from basic `/health/live` and `/health/ready`. It checks enabled automation, content automation and all-workspace agent routines, returning healthy/disabled/degraded/unknown with static status codes and an alert flag.
- Failure inspections log a safe error reference and return that same reference without exposing exception text. No new schema, no SMTP calls and no change to existing readiness routing.
- Actual Render TDD RED: seven 404 failures on `3cf2c69`, initial GREEN seven passes on `b7d9bbd`. Error-reference change at `3e5058c` needs final full QA. Email-worker CLI heartbeat and external alert dispatch remain **unimplemented**, so this is not full A17 closure.


## 2026-10-30 — Typed agent permission request and strengthened QA

- A complete Render SQLite run caught the new permission `PUT` API's untyped raw dictionary (1 failed, 2798 passed); the existing no-untyped-body test correctly failed. D-325.
- Replaced it with strict `AgentPermissionUpdate` in `api/schemas.py` and conversion via `model_dump()`. Added the existing contract regression as an early targeted Dockerfile.review gate. **22 agent/permission tests + typed-body regression passed** on source `851d6de`; full suite pending.
- Existing role, workspace and browser permissions remain unchanged in semantics; no migration or production push.


## 2026-10-30 — Three-level browser-agent permissions (F-06.01)

- Added configurable `allow`/`ask`/`deny` default policy and per-tool overrides for the existing ten declared browser verbs. An explicit global deny cannot be elevated by a per-tool rule or temporary chat grant.
- Owner-only `PUT /api/v1/agent-permissions`; authenticated workspace policy read via `GET`; saved using existing workspace AI settings, including hosted PostgreSQL-backed configuration. Invalid modes, unknown actions and unauthorized writes fail closed.
- AgentRun now checks each selected action before browser execution or cached reads. `ask` returns `needs_permission` with an audit step; `deny` returns `permission_denied`. Scheduled RoutineAgentExecutor also preflights its initial navigation before launching a browser.
- Temporary ChatPermissionGrants are memory-only and expire on close or within one hour; no new schema and no provider egress changes. The attended chat API/UI for granting/ending a chat is not implemented.
- TDD RED collection failure observed, targeted GREEN **20 passed** on 2e9872f; two new initial-goto regressions authored at 27aad6e. Full final QA and upstream signoff pending, **IN_REVIEW**.


## 2026-10-30 — F-06.03 install storage-readiness API

- Added owner-only, read-only `/api/v1/storage/readiness` to classify the existing store inventory and report production blockers; no secrets, URLs, raw paths or customer content.
- Initial 5 tests failed RED on Render without the endpoint and passed after code implementation. Added separate normal-workspace 403 and OS-root mount false-positive security regressions.
- No schema or storage migration and no production validation relaxation; backup Q-29 and store placement S-06.03.06 remain release blockers. Final QA pending.


## 2026-10-30 — Executed A15 stream guard regression (S-06.02.51)

- Render review tested application commit `71fb99c`: **2777 SQLite**, **2797 PostgreSQL**, **215 targeted PostgreSQL** tests passed. Eleven new adversarial video/ASGI cases passed in both Python suites. Concurrency stress 12/12 and desktop/mobile Chromium Contacts accepted.
- The real ASGI guard caps multipart bodies before Starlette parsing, limits in-flight uploads, times out stalled clients and cleans temporary files. This is tested code, **not an independently verified production-wide penetration or load result**.
- Kept A15 S-06.02.51 IN_REVIEW, D-321 open, `main`/production untouched; evidence `docs/evidence/2026-10-30-video-stream-qa.md`.


## 2026-10-30 — Pre-parser video upload security (A15, S-06.02.51)

- Added ASGI guard to both video-media and render multipart routes, before Starlette consumes their bodies. Bounded counted bytes (configured file limit plus 16 KiB multipart overhead), 256 KiB in-memory spool threshold, two in-flight uploads per worker, 30-second idle limit, and deterministic close on disconnect.
- Added real FastAPI HTTP and direct ASGI adversarial regressions for oversized/forged header, early chunked abort, concurrency 429, timeout 408, disk rollover and cleanup; local standalone prototype 11 passed. Full off_CRM suites and Render QA pending at commit time.
- No schema, AI provider, sending or production service change. Cross-process quotas and independent resource-pressure measurements still pending.


## 2026-10-30 — Executed A15 upload QA and dependency audit

- Render QA `dep-dbhqd96i0phs73f1vfrg` executed tested source `0c28d7c`; Python SQLite **2766 passed**, PostgreSQL **2786 passed**, frontend **212 passed**, 215 PG focus passed, Chromium 1280/390px passed.
- The six A15 video-upload tests passed in both Python suites. Scope: handler size, empty upload, authentication and forged Content-Length, not Starlette request-body stream hardening. Leave A15 open.
- Vite high-severity advisories cleared by Vite 8.1.6, but two moderate Vitest development-tool advisories remain open as D-321. See `docs/evidence/2026-10-30-a15-video-upload-qa.md`.
- QA evidence only, no customer/production deployment or board DONE promotion.


## 2026-10-30 — Frontend security gate: Vite patch upgrade

- An actual Render QA build failed at `npm audit --audit-level=high` with **three Vite advisories** on pinned Vite 8.1.4. Updated the project and npm lockfile to patched **Vite 8.1.6** (verified package tarball SHA-512) and compatible dependency ranges; kept existing Rolldown 1.1.5.
- No `npm audit fix --force`, no policy bypass. Re-run `npm ci`, frontend tests/build and npm audits on Render before claiming pass. D-320 tracks the finding.


## 2026-10-30 — Video upload input hardening (F-06.02, A15)

- Added a configured byte ceiling at video-media and render endpoints before media decoding; empty uploads return a clear 400, oversize uploads return 413. Reuses OFFSETX_MAX_UPLOAD_BYTES; no schema or dependency change.
- Added authenticated API tests for both routes, repeated oversized requests, bounded reads, forged Content-Length, missing credentials, and real WebM happy path.
- **IN_REVIEW, pending Render QA.** Multipart pre-parser spooling and aggregate concurrency/disk caps remain open as A15; not a production security clearance.


## 2026-10-19 — QA verified review (docs only)

- Code commit `54864b0b` passed 212 frontend, 2760 full SQLite, 2780 full PostgreSQL, 215 storage PostgreSQL, 67 CI/verifier tests and 12/12 concurrency stress repeats. Chromium Contacts passed at 1280px and 390px; both npm audits reported 0 vulnerabilities.
- Repaired D-317/D-316 log record separation (D-318) during evidence handoff. No application code or database migration in this follow-up.
- F-06.19/F-06.20/F-06.21 remain IN_REVIEW. See `docs/evidence/2026-10-19-render-qa-54864b0.md` for exact evidence and open production gates.


## 2026-10-19 — CRM operations correctness and review tests (IN_REVIEW)

- F-06.20: prevent pre-outreach inbound messages from inflating campaign reply rate; keep JSON contract stable and clarify chronology in UI and documentation (D-317).
- F-06.19: add Sales Tracker workspace-overlap isolation regression.
- F-06.21: add reopen-follow-up counter regression.
- No schema migration, live sending or production deployment; full application tests, browser/PG review and board verifier remain required. See `docs/evidence/2026-10-19-crm-operations-review-checkpoint.md`.


## Unreleased
- **2026-10-16, off_CRM review acceptance:** added authentic 503-contact pagination regression across six authenticated API pages and real CSV/XLSX formula-injection checks covering accepted/rejected/raw/decision/metadata tabs without mutating input; 19 affected tests passed on Render. Added disposable Chromium 1280/390px contacts import, navigation, search acceptance gate; its final green build is still required. Failures from test timing (D-315) and duplicate Import contacts selector (D-316) were recorded, not suppressed.
- **2026-10-16, concurrent CRM response integrity (D-314):** a 40-create/8-worker recovery test intermittently returned HTTP 404 or reported IDs inconsistent with persisted rows after restart. The CRM read helpers now hold their existing SQLite RLock across statement execution, cursor fetch and materialisation, not only through `execute`. Added deterministic cursor-lock ownership test and strengthened per-response and restart-set assertions; deterministic test and 12x40 focused stress passed in preliminary Render verification. The full cross-backend regression and review release gates remain open until final build evidence is logged.

- **2026-10-15 D-313 security remediation (S-06.02.21):** independently identified a real linked-product cross-workspace disclosure from an unset request context being equated with the content timer's owner authority. Reproduced red, then changed the shared reader to deny missing principals. Only the authorised content scheduler/manual install-owner action now installs a try/finally-reset scoped timer identity, carried into `asyncio.to_thread`. Tests check rejection without a principal and authorised timer access, plus no scope leakage. Repaired a previously stale GTM test expecting the unsafe behaviour; no permission bypass. Decision DD-121, evidence in `docs/evidence/S-06.02.21-security-review-2026-10-15.md`.
- **Final verified regression at Render `dep-db8cnnou01pc73fb3d8g`:** 3 targeted security/GTM tests passed; 67 CI/verifier fixture tests passed; full SQLite **2754 passed, 45 skipped**; real disposable PostgreSQL 17 storage **215 passed**, copied-session revoke **1 passed**, full CRM-on-PostgreSQL **2774 passed, 94 skipped**. Earlier frontend clean 212 Vitest, successful build and both 0-finding npm audits still valid. Story remains IN_REVIEW pending authentic Git-history board verifier, CI runner, independent security review and real browser/recovery acceptance.

- **Verified 2026-10-15 S-06.02.16 dependency remediation:** reproduced 5 npm development advisories (2 high, 3 moderate), used a networked npm `package-lock-only` installation to upgrade pinned Vitest 4.1.11 and transitive packages, and committed synchronized frontend manifests. Render review build `dep-db8akqs9v7es73877d9g` passed clean `npm ci`, all 212 React tests, Vite build, production npm audit **0 vulnerabilities** and development npm audit **0 vulnerabilities**. No audit was suppressed or bypassed.
- **Verified full repo QA, 2026-10-15:** real Git-fixture/CI verifier suite **67 passed**, full Python suite **2,752 passed, 44 skipped, 44 warnings**, zero failures on disposable Render review runner. Prior 72 Python failures are historical and superseded by this clean rerun, but PostgreSQL-specific skips, original Git-ancestry check, hosted backups, end-to-end browser and independent review gates remain. A separate QA app was deployed, confirmed Uvicorn startup and HTTP 200, with QA PostgreSQL active connections. Main production service is unchanged.

- **2026-10-15 review verification:** isolated Render runner exercised 86 focused CRM Python tests (86 passed, 14 PostgreSQL-only skipped), 352 security/workspace/browser/hosted-storage tests (352 passed, 15 skipped), 559 agent/GTM/email/video/API security tests (559 passed, 2 skipped), and 187 crawler/extraction/meeting/usage/trace tests (187 passed, 44 warnings on final rerun): **1,184 focused Python test executions passed**, and 212 frontend tests passed. The full Python 2,796-case run earlier recorded 72 failures, including Git-context gaps; those are **not** claimed resolved by focused passes. npm development audit remains failed with 5 advisories (2 high, 3 moderate). Neither the production deployment nor board DONE statuses was changed.
- **Egress-log copy reliability fix:** `copy_egress_log` now rejects a missing SQLite source **before** trying to connect to remote PostgreSQL, preserving an actionable error and avoiding unnecessary connection attempts. `EGRESS_COLUMNS` now matches the declared schema including `system_prompt`, protecting explicit cross-engine copy ordering; regression tests passed in Render (352-pass security/storage wave). No schema migration was introduced.
- **Acceptance test repairs:** corrected stale FastAPI HTTP 400/422 expectations, SQLite 10/11 migration assertion, workspace-owner safety fixture, supported image/video campaign kind, and a random-UUID ordering assumption. Documented D-298–D-311 in `DEFECT_LOG.md`. The complete 80-item outstanding register and individual results live in `docs/evidence/2026-10-15-pending-80-item-register.md`.


- **F-06.16 Unified CRM Search** (IN_REVIEW, 2026-10-15): authenticated, paged cross-campaign contact and existing Sales Tracker search by name/email/company; escaped literal queries and matched campaign/member navigation. No message-body search.
- **F-06.17 Account Intelligence Workspace** (IN_REVIEW): company grouping by normalized exact name, count-safe contacts/campaigns/leads and company view with message/task coverage. No unverified firmographic enrichment or company merger.
- **F-06.18 Campaign-to-Revenue Attribution** (IN_REVIEW): source-backed first-campaign-link attribution, one credited sales lead per deal, qualified-reply/lead/won and recorded cash figures with explicit noncausal label and no FX guessing.
- New CRM insights API and three React pages plus Python/frontend tests authored. No schema change and no external sender/provider use. Full test suites/PostgreSQL/Chrome/security review remain execution gates.


- **F-06.13 Qualified Reply-to-Sales Conversion** (IN_REVIEW, 2026-10-15): explicitly convert reviewed Positive/Meeting incoming replies into deduplicated Sales Tracker leads. Link saved campaign membership; reuse existing same-email lead without rewriting it; fail closed on multiple duplicates. No automatic sending.
- **F-06.14 Contact 360 Workspace** (IN_REVIEW): campaign-scoped and privacy-allowlisted identity, reply, task and opportunity overview, accessible from Contacts, Reply Inbox, Follow-ups and Today's Priorities.
- **F-06.15 Daily Action Command Center** (IN_REVIEW): read-only ranked worklist of overdue tasks, replies requiring triage and stale/unworked linked sales opportunities; accurate filtered counts and pagination.
- Added CRM SQLite schema v11 and PostgreSQL step 3 for campaign_sales_links; updated CRM inventory to 34 tables and related test source. Backup/migration/restore and full tests are mandatory gates; not run in this connector-only session.


- **F-06.10 Reply Inbox & Human Triage** (IN_REVIEW, 2026-10-14): authenticated per-campaign reply inbox, review/outcome classification, metadata-only events, and linked human follow-up creation. Triage does not resume or send messages.
- **F-06.11 Contact Communication History** (IN_REVIEW): campaign-membership scoped inbound/outbound message timeline with bounded subject/body, SQL-level pagination, no raw provider JSON and new Contacts/Reply Inbox access.
- **F-06.12 Human Follow-up Task Manager** (IN_REVIEW): durable task list and create/edit/complete/reopen, due dates and display-only assignments, stale-revision 409 protection. Additive two-table SQLite v10 and PostgreSQL CRM step 2 migration; hosted backup/restore a release gate.
- New Python/Vitest and hosted-store count/migration test source prepared. **Not executed**: CI jobs previously terminated with zero steps; SQLite/PostgreSQL, full suite, browser and restore acceptance remain required.


- **Audience Management Workspace** (`F-06.07`, IN_REVIEW, 2026-10-14): manual contact entry with deduplicated email linking, explicit at-most-100-row batch mark/unmark/stop and confirmation; existing imports, sender and contact editor remain unchanged. API and frontend tests authored; not executed.
- **Campaign Launch Readiness Center** (`F-06.08`, IN_REVIEW): nonmutating campaign preparation checks for active status, audience, approved/due candidates and daily cap. It does not certify external mail, consent, suppression, provider availability or final send preflight.
- **Campaign Activity & Audit Timeline** (`F-06.09`, IN_REVIEW): campaign event facets, exact server event-type filtering, 50-row paginated accessible history and allowlisted visible metadata. Existing event response remains compatible.
- **Verification remains open:** focused/full Python, frontend build/SPA, PostgreSQL, browser and independent review were not executed in this connector-only environment. GitHub Actions jobs previously failed before executing any steps. No release claim.

- **Campaign Management** (F-06.04, IN_REVIEW, 2026-10-13): editable campaign settings, IANA timezone validation, explicit typed archive, safe paused restore, status controls and frontend/API regressions. Email-specific settings stay within email campaigns.
- **Campaign Blueprint Reuse** (F-06.05, IN_REVIEW): create an idempotent paused configuration-only clone from an existing campaign; no copied recipients, drafts, messages, history or credentials; regression and restart checks authored.
- **Campaign Performance Intelligence** (F-06.06, IN_REVIEW): on-demand CRM-based campaign metrics, unique-contacted denominator, replies from contacted recipients, unsent/pending and stopped state plus draft counts. No model generated statistics.
- **Release gate**: tests are authored but not run by this connector-only session; GitHub Actions still fails before any job steps. These features are committed for review, not DONE/deployed.


- **Bounded Send Queue screen** (`S-06.02.47`, IN_REVIEW, 2026-10-13): authenticated queue API now accepts a bounded page and returns only that page's contact details; the backend sender retains its separate full-campaign queue. New accessible Previous/Next controls; Python/TypeScript tests authored, not run.
- **Honest campaign-wide Send Queue totals** (`S-06.02.48`, IN_REVIEW): Ready, Needs approval and Replied cards use whole-campaign classification, including future-scheduled drafts and terminal statuses, independent of page/view. Ready means review candidate only; live send preflight still applies. No real provider/postgres/runner proof yet.
- **Action-focused queue views** (`S-06.02.49`, IN_REVIEW): All, Approved and due, Needs approval and Replied cohorts have validated query values, correct paging and contextual empty states. This is read-only and does not bypass live-send approval.


- **Security containment for A07/A08** (`S-03.01.03`, `S-05.01.04`, 2026-10-13, IN_REVIEW): production BrowserBox refuses Docker bridge before launch because it cannot prove private-IP egress isolation; JS-based Crawl4AI public fetching refuses browser startup until a verified gateway/firewall exists. Nonproduction bridge remains insecure; safe_http stays available. Added regression tests; no full suite or live Docker/Chrome test run.
- **Production audit follow-up** (`S-06.02.23`, 2026-10-13, IN_PROGRESS): A07/A08 containment status updated; A25 source-checked as still open because render.yaml contains web services only and no durable email worker. No full audit verification or worker rollout.

- **GTM real-case uniqueness guard** (`S-12.02.05`, D-269, 2026-10-13, IN_REVIEW): a minimum 30-case suite now requires distinct case IDs as well as the explicitly judged-real label. Add a repeated-case regression; no real corpus or executable full-suite results yet.

- **GTM controlled A/B correction** (`S-12.02.05`, D-268, 2026-10-13, IN_REVIEW): separate expert references from baseline product/campaign notes. Ablation now removes expert notes and the winning template without discarding product facts. The three synthetic GTM examples and packaged suite use the new key; new regression check is committed, unrun. The full suite and live A/B remain unverified.

- **Video product-aware direction and prompt audit** (`S-12.01.03`, 2026-10-13, IN_REVIEW): video director sends linked product facts and owner style through classified broker fields; constant system instructions; bounded `system_prompt` field in all text-call egress logs with additive SQLite/Postgres migration and tests. Full regression, provider and deployment verification still required.
- **Frontend dependency audit enforcement** (`S-06.02.16`, 2026-10-13, IN_REVIEW): npm audit production and development gates added to CI with regression coverage. The npm registry-backed audit could not run and specific dependency findings are unresolved/unknown; not a clean bill of health.
- **Reference-informed GTM strategy** (`S-12.02.05`, 2026-10-13, IN_REVIEW): optional expert retrieval and workspace winning templates go through classified fields, A/B removes reference fields only, and GTM eval cases check plan structures. Three synthetic starter cases explicitly cannot qualify for a trusted model-promotion verdict; owner corpus and 30 judged real cases remain absent.

- **Explicit installation-owner login** (`S-06.02.36`, 2026-10-13, IN_REVIEW): creating a `local` workspace login over the authenticated API now requires a strict explicit owner-confirmation boolean. Existing accounts and bootstrap unchanged; endpoint regression tests committed, not executed.
- **Correct workspace lock for CLI targets** (`S-06.02.28`, 2026-10-13, IN_REVIEW): cli_workspace_leases discovers existing restore lock sidecars along resolved target-file ancestors; DB, Outreach, Notebook and Artifacts callers now consult real paths. Common .env defaults used across CLIs. Cross-process restore/CLI proof and full suites pending.
- **Provider usage on Connectors** (`S-06.02.34`, 2026-10-13, IN_REVIEW): local counted calls shown with or without a cap; on-demand key-scoped OpenRouter per-key limit and DeepSeek account balance checks with timestamps; provider reporting support declared in registry. Other providers are not guessed; rate-limit header capture and live vendor validation remain open.

- **Network audit A07** (`S-03.01.03`, 2026-10-13, IN_REVIEW): browser policy now rejects private/non-global IPs, alternate numeric IP spellings and local DNS suffixes in either mode; added guard regression cases. Docker bridge egress remains unrestricted and must be isolated before security can be certified.
- **Crawler DNS-rebinding audit A08** (`S-05.01.04`, 2026-10-13, IN_REVIEW): Requests now connects to its checked public DNS IP with Host/SNI/TLS hostname retained; tests cover DNS mutation, refusal and proxy bypass. Crawl4AI/browser-rendered fetching still needs a network-level boundary and end-to-end validation; no release claim.

- **Skip link keeps current CRM screen** (`S-06.02.37`, 2026-10-13, IN_REVIEW): prevent the skip-link's `#main-content` anchor from rewriting the hash router to Dashboard; focus and scroll main without navigation, with Settings and Contacts regression cases. Full frontend/browser suite remains unrun.

- **Shallow Git ancestry verification** (`S-06.02.20`, 2026-10-13, IN_REVIEW): board verification now identifies insufficient history and says `git fetch --unshallow`, instead of falsely accusing historical evidence. Adds real depth-one clone regression and requires full-history checkout for both GitHub Actions jobs. Three isolated Git tests passed; the repository suite and CI remain unrun.

- **Accept short low-bitrate WebM exports** (`S-06.02.39`, in review, 2026-10-12): valid 2-second VP9 videos no longer fail only because they compress to fewer than 4096 bytes. Small WebM files now need evidence of real video blocks; metadata-only and malformed exports remain refused. Added a real independent 60-frame VP9 fixture and targeted tests. Isolated sample/ffprobe checks passed; full Python, frontend and browser validation remains open.

- **A07/A08 source recheck** (2026-10-11, `S-06.02.23`): browser private-network exclusion and public-fetch DNS validation remain incomplete on `develop`. Logged `D-266` and `D-267`, added `S-03.01.03` and `S-05.01.04` with security acceptance work orders and traceability. No production code was changed, and full network or test-suite execution remains unverified.

- **Production audit recheck started** (`S-06.02.23`, 2026-10-11): the
  September audit now tracks the status of all 35 findings against `develop`.
  Earlier remediations are deliberately not marked reverified; six known gaps
  remain explicitly open, and 21 findings await direct reproduction. Current
  CI jobs fail before running steps, so there is no new application-test or
  release claim. The linked work order records what is needed to close them.

- **Posting from an applied plan** (`S-12.02.06`, in review): Apply declares a
  paused posting/image pair and its daily rate; Posting connects local-outbox
  accounts, starts a plan, previews drafts, and offers approval/scheduling or
  Skip. Proposals are bound to their plan, account caps still bind, and paused
  pairs retain queued posts. Missing or foreign media cannot publish. Restart
  and previous-revision data-read checks passed; browser and live drafting
  verification remain open. Social adapters are still unavailable.

- **Traceable failures** (`S-06.02.38`, in review): failed API requests expose
  a reference matched to a secret-safe JSON record. Worker/job status and
  command failures carry references too. Local logs rotate under the data
  directory; Render uses stdout. Recovery leases still protect the workspace.
  Unexpected command errors return nonzero and unexpected request errors
  return a structured 500 rather than a successful fallback. Independent code review and local checks passed; Chromium, CI and hosted
  verification remain gated. Timer status is displayed in Settings and Posting;
  routine scheduler status remains readable independently of run history.

- **Screens open at their top** (2026-10-04, `S-06.02.25`). Navigation keeps
  keyboard focus on the main content without scrolling it beneath the sticky
  bar, then resets the page to its top. Campaign warnings stay visible at
  desktop and phone widths, including warnings arriving after navigation.
  Fixes `D-137`; campaign selection and initial-load safety gates are unchanged.


- **The CRM outlives the disk too** (2026-10-03, `S-06.03.03`, DONE). With
  `OFFSETX_DATABASE_URL` set, campaigns, contacts, drafts, sends, replies and
  delivery jobs live in that database, on SQLite and PostgreSQL alike — for the
  web app, the email worker, `offsetx-outreach` and `offsetx-notebook`, which
  all open the same CRM; a `--db` given on the command line still wins. A
  server whose own disk still holds a CRM file with your data asks once:
  `offsetx-db import-crm --yes` copies it in, `--skip` starts without it.
  `offsetx-db copy-crm --from X --to Y` copies a whole CRM either way, into an
  empty one only, and checks every table's count. Fixed on the way: the email
  worker failed on PostgreSQL every time it put a job back to wait for its
  send window (`D-221`); a closed database connection quietly reopened itself
  (`D-222`); `offsetx-db copy-log` printed its database URL with the password
  (`D-225`); a PostgreSQL URL given as the CRM's file path became a file named
  after it (`D-217`). Search in the CRM ignores capital letters on PostgreSQL
  as it always did on SQLite. The sidebar and Settings now say where the CRM
  really is — they said "SQLite on this device" whatever was true (`D-226`).
  After review: the import works even when the worker or a deploy started on
  the database first, and the worker and tools wait, as the app does, while
  a local CRM is left behind (`D-227`); a copy stops on a value PostgreSQL
  would change (`D-228`); a write waits at most 5 seconds for another
  (`D-229`); a watching worker rides out a database that is away (`D-230`)
  and takes a URL as `--database` (`D-238`); the database's address and any
  password option are shown to the install owner only (`D-232`).
  Not yet: backups of the hosted database
  (`S-06.03.04`); expert-library search is unranked on PostgreSQL.

- **The hosted storage, reviewed and DONE** (2026-10-02, `S-06.03.01`,
  `S-06.03.02`). Only a PostgreSQL URL is accepted, and never repeated back
  (`D-206`). A paid answer is never thrown away by a usage-counter read
  (`D-207`). A silently dropped connection is noticed in about 15 seconds
  (`D-208`). Signed-in screens show a sentence during an outage, and the app
  recovers by itself when the database returns (`D-209`). An install with its
  own disk is asked once, with `offsetx-db import-local --yes` or `--skip`,
  what happens to the keys and logins already in its data folder (`D-210`). A
  database blip is never blamed on a provider (`D-211`). Also `D-212` to
  `D-216`.

- **Keys, settings and logins can outlive the disk** (2026-10-02, `S-06.03.01`,
  `S-06.03.02`). Set `OFFSETX_DATABASE_URL` to any PostgreSQL 13 or newer —
  Neon or Render now, AWS or Azure later — and `OFFSETX_SECRETS_KEY` to what
  `offsetx-db new-secrets-key` prints. Provider keys (encrypted), AI settings
  and trust, the counters behind each daily limit, workspace logins and the
  egress log then live in that database. A missing or wrong key stops the start
  with what to do. `offsetx-db inventory` lists every store and where it lives.
  Hosted stores now reopen a dropped connection (`D-199`) and daily limits no
  longer restart at a Render spin-down (`D-198`). The CRM itself moves next
  (`S-06.03.03`).

- **The sixth check, closed** (2026-09-28). Confirm now goes exactly where the
  button you pressed says (`D-194`): a waiting profile can always be confirmed
  as yours — its key proves it — or, if its label names a client workspace,
  returned to that workspace; each button says which, for screen readers too
  (`D-195`). Each button sends its own choice, so older browsers get it right,
  and Enter in the key box no longer picks for you when there are two
  (`D-197`). Filed, not fixed: a login made in workspace `local` acts as the
  install owner with nothing asking for that (`D-196`, `S-06.02.36`).
  `S-06.02.31`, `S-06.02.32` and `S-06.02.33` are DONE. The last two fixes were
  checked by tests and a real browser walk, not by another fresh review.

- **The fifth check, closed** (2026-09-26). The fourth reviewer confirmed its
  six findings fixed, and found one regression in the fix: with a client
  workspace named "default", confirming your own old "default" profile gave it
  to that client (`D-190`). "default" is always yours now, and each Confirm
  button says where it puts the profile. Also: a key-less profile's refusal
  says the true reason (`D-191`), the damaged-master-key advice names both files
  (`D-192`), and the Models panel says when a save cut your level (`D-193`).

- **The fourth fresh-context review, closed** (2026-09-26, `S-06.02.31`,
  `S-06.02.33`). Nothing critical or high; two medium, four low, each fixed
  with a test that failed first.
  - **Confirming an old profile takes the key saved in it** (`D-185`). Its label
    proves nothing — before `05e9738` a client's own saves could read "default"
    too — but a client's planted profile holds a key you do not know. A profile
    with no key stored offers only Remove (`D-187`).
  - **The form offers only what your trust allows** (`D-184`), so nothing you
    choose is cut when saved, and a cut from the API is reported. Its hint says
    what the level means right now: by your grant, while you have lowered the
    provider, or at its tier.
  - **Smaller**: a grant only ever lifts what is sent (`D-186`); a provider whose
    models are all blocked "Sends: Nothing" (`D-188`); every damaged-key message
    says what the install owner can do, and that removing the keys file clears
    every workspace's keys (`D-189`).

- **The third fresh-context review, closed** (2026-09-26, `S-06.02.31`,
  `S-06.02.33`). Nothing critical or high; two medium, five low, each fixed
  with a test that failed first. Its random test — 2,800 sequences of connect,
  save, grant, withdraw and trust changes — found lowering trust never raised
  what any model is sent, and still finds none after these fixes.
  - **Your "How much to send" level is never overwritten** (`D-176`). The
    full-data grant used to write "full" into it, so withdrawing after a raise
    kept sending full data, and a save made while the grant was paused cut it
    for good. The grant now decides what its models get while it stands, and
    your level waits underneath.
  - **Old provider profiles have a screen** (`D-177`). Settings lists the ones
    saved before off_CRM recorded whose each one is, with where each sends, to
    confirm or remove; Drafts says how many wait. *(Corrected 2026-09-26: this
    entry first said a client's key could not end up in your drafts. It could:
    before `05e9738` a client's own saves could be labelled "default" too
    (`D-185`). Confirming now takes the key the profile holds.)*
  - **Smaller**: disconnect works even when stored keys cannot be read, and the
    error says what to do (`D-178`); "Sends" and the grant follow the models you
    switched on (`D-179`); at most 50 models, and 50 per-model trust settings,
    per provider (`D-180`); confirming goes by the profile, not by a cookie
    (`D-181`); an edit checks ownership as it writes (`D-182`).

- **The second fresh-context review, closed** (2026-09-25, `S-06.02.31`,
  `S-06.02.33`). Six findings, each fixed with a test that failed first.
  - **Your drafts could run through a client's profile** (`D-165`, high). The
    install owner's "automatic fallback" used every workspace's provider
    profiles, so a client could add one at the top of the list, pointed at its
    own server, and receive your contacts. A draft now uses only the caller's
    own profiles, and a request can no longer choose whose.
  - **Whose a profile is, is now the server's record** (`D-166`, `DD-68`). It
    was a label the request supplied — "default" from the old form — so a
    workspace named `default` owned your profiles and key. Profiles saved
    before this wait, in no draft chain, until you confirm them:
    `POST /api/v1/provider-profiles/<id>/confirm` as the install owner. The
    `owner` field and the draft's `provider_owner` are refused now, with a
    sentence saying the server decides.
  - **The full-data grant works, and lowering trust never raises what is
    sent** (`D-167`, `D-171`, `DD-67`). The grant never sent more — Connect
    ignored it — and "Allow anyway…" sat only on blocked providers, which
    receive nothing at any level. It is now **Send full data to … anyway…**
    under Change settings, where it can change something; it reaches only
    models trusted at the provider's default or higher, and it pauses while
    the provider is lowered. Before, lowering NVIDIA handed the grant to the
    Chinese-built model capped there.
  - **Smaller**: the provider call log shows a client only its own calls
    (`D-168`); disconnect takes the key in the same step as the connection
    (`D-169`); a click that changes nothing records nothing, and trust reasons
    are capped at 500 characters (`D-170`); the card's limit and "Sends" follow
    your trust, not the config default (`D-172`).
  - **Found, not fixed**: the Drafts screen's model option points at a profile
    form no screen has had since providers moved to Connectors (`D-173`).
    Which way drafts should go is your call (`Q-28`, `S-06.02.35`).

- **Trust is yours to change, per provider and per model** (2026-09-25,
  `S-06.02.33`). Every provider card has a trust choice, and "Trust per model"
  lists each model. Lowering is instant; raising asks why and records it with
  who made it. A model is trusted as much as its provider or less — blocking
  a provider blocks every model on it — and a model built elsewhere stays
  capped until its own setting lifts it, with a reason (`DD-65`, amended).
  "Who decided" is the login, never what a request claims (`D-152`).
  - **The fresh-context review found two critical holes in older code**, now
    closed: any login could make the server send any of its environment
    variables to a URL of its choosing (`D-154`), and could re-point the
    owner's provider profile to receive the owner's key (`D-155`). It also
    found the first trust rule let a blocked provider's model still be used,
    and eight smaller faults (`D-156` to `D-164`); each fixed test-first.

- **Keys only from the app, and limit presets** (2026-09-25, `S-06.02.31`,
  `S-06.02.32`). A provider key set in the server's environment used to
  answer for every workspace login, other clients' included (`D-151`); that
  route is gone, and connecting with no key says to paste one. The call and
  spend caps are now chosen from presets — the provider's own limit or no
  cap, three sizes, or a typed number.

- **Connecting a provider from the screen works again** (2026-09-25,
  `S-06.02.30`). The Connectors form sends a call cap of 0, meaning "the
  provider's own limit", and a strict contract added on 22 September refused
  it, so every Connect said "Request validation failed" (`D-149`). And that
  message now names the field and what was wrong, everywhere (`D-150`).

- **Two live bugs the owner reported** (2026-09-25). NVIDIA's reasoning model
  failed every chat with a 400, because we sent an option its server refuses
  (`D-147`, `S-06.02.29`). And every Render deploy timed out: the host guard
  answered 421 to Render's own health checker (`D-148`). Health checks are
  now answered on any host; the API is still guarded; Render's own hostname
  needs no setting.

- **Command-line tools no longer write under a restore** (2026-09-24,
  `S-06.02.24`). `offsetx-outreach`, `offsetx-notebook`, `offsetx-evals`,
  `offsetx-tools`, `offsetx-db` and `offsetx-artifacts` hold the workspace's
  shared lease for a whole command, as web requests and the email worker do.
  While a backup or restore runs, or an interrupted restore awaits rollback,
  they refuse to start and say which, instead of writing into files the
  restore is swapping out (`D-134`, `D-139`). Commands that open nothing still
  run. Run from the web app's folder with its environment, the tools also open
  its files by default: the Gmail token, the egress log and the notebook's AI
  context (`D-138`, `D-141`). `.env.example` and the README no longer pin the
  CRM database and Gmail token outside `OFFSETX_DATA_DIR` (`D-140`).
  - **The fresh-context review** found a root-owned lock file could put every
    API request at 500 (`D-142`, high), and three smaller gaps (`D-143` to
    `D-145`); all fixed with tests that failed first. Still open: a tool
    pointed at the web app's files from another folder, or with
    `OFFSETX_DATA_DIR` only in `.env`, locks the wrong workspace (`D-146`,
    `S-06.02.28`) — run the tools with the web app's environment, from its
    folder.

- **The remaining work, planned for handoff** (2026-09-23). No code: every open
  item is on `BOARD.md` with a `work_order:` line naming the plan an
  implementer follows. New: work orders for seven stories
  and the close-out of `S-06.02.21`/`S-06.02.22`; the CRM tenancy design for
  `S-06.01.06`, ready for the owner's answer to `Q-27`; stories `S-06.02.25`,
  `S-06.02.26`, `S-06.02.27`; defects `D-137`, `D-138`.

- **The cold review of `develop`** (2026-09-23): ten findings, each fixed with a
  test that failed first, and two filed.
  - **Critical — backups were anyone's.** Any workspace login could export the
    whole install — the install token, the session-signing key, every login and
    AI key — or restore over it. Only the install owner can now: the token, or
    the install's own login (`D-124`).
  - **One workspace could read another's product** by drafting a campaign that
    workspace had linked, and could run the owner's content timer on the owner's
    keys. The draft writer now reads with the caller's workspace and refuses
    another's; the timer is the owner's to run and configure (`D-125`).
  - **Data kept, both ways.** An external CRM database no longer has its WAL
    replayed over the other generation on a restore or rollback (`D-126`);
    Docker Compose mounts the data where the image now keeps it, and the CLIs
    open the web app's database (`D-127`).
  - **Also fixed:** backups on Python 3.10, where the whole suite now passes
    (`D-128`); the app starting while the email worker runs, and the worker
    refusing a half-restored workspace (`D-129`); Settings reachable when the
    campaign list will not load (`D-130`); the tool registry's connections
    closed on restore (`D-131`); `api_token=`-style secrets in prompts
    (`D-132`); a backup no longer holds every request at 503 behind a long
    scheduled run (`D-133`); the top bar says "API access needed" only when
    access is the problem (`D-136`).
  - **Filed:** the CLIs write without the restore lease (`D-134`,
    `S-06.02.24`); CRM rows belong to no workspace (`D-135`) — the owner's
    decision, `Q-27`.
  - **The old branches are not deleted yet.** GitHub refused this session both
    the archive tags and the deletions (HTTP 403).
    `scripts/archive_old_branches.sh` does both safely, from a clone with push
    rights; `S-06.02.19` waits on it.

- **One working branch, `develop`** (`S-06.02.19`, 2026-09-23). Every line of
  built work was merged or ported onto one branch; the rest are to be kept as
  `archive/<branch>` tags and deleted (`docs/BRANCHING.md`). `main` is promoted from
  `develop` after checking; both run on Render as free services.
  - **The newest line passed none of its own checks.** It had never run its
    suite: 33 tests failed and 5 files could not load. Fixed at the cause, each
    logged: every privacy route crashed (`D-103`); strict request schemas hid
    readable errors and refused requests the screens send (`D-107`); timers
    crashed on a missing login (`D-109`); a bare `token=` reached a model
    provider (`D-110`); workspace-login installs could not start (`D-111`);
    and several tests were checking nothing (`D-104`, `D-105`, `D-108`).
  - **Durable state and safe recovery** (`S-06.02.21`, ported). Backups now hold
    the whole workspace, so no store can be forgotten (`gtm.db`, images, video
    and posts were); a restore drains requests, swaps the folder under a
    journal, reopens every service and rolls back on failure; the old restore's
    stale-WAL data loss is gone (`D-114`). `OFFSETX_PRODUCTION=1` refuses to
    start on `/tmp` or without the disk. The Docker image builds again — it did
    not, on `main` either (`D-116`) — installs the lock with its extras, and
    runs as an unprivileged user. `/health/ready` checks what it claims to.
  - **Campaign selection** (`S-06.02.22`, ported). A newly created campaign
    stays selected; before, the stale list put an older one back (`D-123`).
  - **Also fixed:** the Connectors screen called an API route that never
    existed (`D-120`) — a new test now checks every path the screens call;
    nested transactions crash no more (`D-117`).
  - **Merged:** reports and artifacts (`S-07.01.04`, IN_REVIEW), the
    competitor research, the frontend-audit blocker record, and the owner's
    production contract in `AGENTS.md` and the Definition of Done.
  - **Renumbered:** D-80/D-81 → D-100/D-101, the reports branch's DD-21/D-51 →
    DD-34/D-102, and the ported stories' IDs; `docs/BRANCHING.md` lists them.

- **The GTM engine, Phase 1 and 2** (`E-12`: `S-12.01.01`, `S-12.01.02`,
  `S-12.02.01`–`S-12.02.04`). Design and work orders:
  `docs/architecture/GTM_ENGINE.md`.
  - **ProductTruth.** The owner describes the product once on the **Product**
    screen: name, one-liner, audience, problem, offer, proof, and the claims it
    must never make. Email templates fill `{product_*}` from it; a post pipeline
    uses its one-liner as the angle, resolved *before* the data class is chosen;
    a draft that says a forbidden claim is flagged.
  - **Plan.** The **Go-to-market plan** screen turns a goal (replies or views)
    into a plan. A model chooses from declared lists and writes short
    sentences; code decides volumes from what is actually connected, the stream
    (always targeted outreach) and what gets removed. No model connected means a
    rules plan and a sentence saying why — never an error.
  - **Apply.** A plan becomes **paused** campaigns, one per channel. It imports
    nobody, spends no Apollo credit and sends nothing. Applying again resumes a
    half-finished apply instead of duplicating it.
  - **Review.** An applied plan is measured and gets one finding per channel,
    in a fixed order: delivery health first, then whether it is running, then
    volume, and the copy last — only after 20 people were contacted, and by a
    90% Wilson interval rather than a threshold. A model may only pick among the
    remedies each finding permits.
  - **Revise.** A review becomes the next version: the measured reply rate
    replaces the assumed one, the deadline stays, and applying it updates the
    same campaigns. Each version is judged on its own sends.
- **Fixed on the way:** the plan's capacity counted a disabled social account
  (`D-83`); the pacer steered by a campaign's oldest views goal instead of its
  newest (`D-84`).
- **Fixed after a cold review** (`D-87`–`D-99`): **pausing a posting campaign
  now stops posting** — its due posts wait, still scheduled, and content
  automation makes nothing for a paused pair (`D-87`, `DD-57`); a plan's angle
  now reaches posts and any template that says `{product_angle}` (`D-89`); a
  campaign deleted from the CRM is made again instead of blocking the plan
  (`D-90`); campaigns are paused before they are linked (`D-91`); "Never claim"
  survives the payload's length limit (`D-93`); and the Product screen's
  "New product", unsaved ticks and dead links behave (`D-99`).
- **For the owner to decide:** below `full`, the payload filter hides the plan's
  numbers from models (`Q-25`). The brain still works — its arithmetic is code —
  and a test holds that the codes a model chooses from survive the filter.
- **Filed, not fixed:** a plan's posting channel cannot reach a published post
  from the screens (`D-82` → `S-12.02.06`). Apply's next steps and the review now
  say so plainly instead of implying "connect an account and resume" is enough.
- **Corrected advice:** the scraper stack in `GTM_ENGINE_GAP_ANALYSIS.md` had
  recommended stealth tools (Camoufox, Patchright, Scrapling's
  `StealthyFetcher`, Firecrawl as a way past protection). They are removed:
  `DD-04` forbids anti-bot evasion.

- **CHECK-mode hardening closed D-79, D-100 and D-101 across the next production
  review batch.** S-06.02.01 now blocks generic credential assignments and field names such as
  `api_key`, `client_secret`, `secret_key` and `api_secret` before
  provider I/O even when the value has no known vendor prefix. S-06.01.01 now serializes workspace AI settings/key read-modify-write
  operations across processes while retaining atomic file replacement, and its
  username validator now rejects the intended control characters instead of
  ordinary letters/digits. S-06.01.04 was cold-reviewed end to end; its
  attended-target refusal and verified-notification-only path match the backlog
  contract, so no speculative code change was added. Focused regressions are
  committed; executable evidence remains blocked before CI step 1, so all three
  stories remain IN_REVIEW.


- **CHECK-mode hardening closed D-76, D-77 and D-78 across the next-three
  review batch.** S-06.02.04 now re-inventories a previously successful privacy
  store before trusting its old receipt on retry, so newly written subject data
  cannot survive behind stale success. S-04.01.01 now disables the CRM memory
  store's implicit global-memory merge for companion runs, preserving exact
  memory scope in production as well as tests. S-02.02.02 now marks directories
  once PLAN management begins and refuses to regenerate a missing managed
  PLAN.md, preserving owner steering across restart. Focused regressions are
  committed; executable evidence remains blocked before CI step 1, so all three
  stories remain IN_REVIEW.

- **S-05.01.03 now fails cleanly if its mapped recipe disappears.** Catalogue
  `UnknownRecipe` is translated at the teardown boundary into the controlled
  domain error already handled by the API, closing D-74 without changing recipe
  selection or the catalogue itself. The story remains IN_REVIEW pending
  executable evidence.

- **S-05.01.03 competitor evidence now rejects NaN and Infinity.** The shared
  numeric validator requires finite values before applying the existing
  non-negative rule, preventing malformed duration from crashing timeline tick
  conversion and preventing non-finite performance evidence from escaping.
  This closes D-73. Repository execution evidence is still blocked before CI
  step 1, so the story remains IN_REVIEW.

- **S-05.01.02 extraction-pack configuration now fails closed on malformed CSS.**
  The registry validates record and field selectors with Scrapling's own parser
  before installing a pack and rejects pack-supplied pseudo-elements, leaving
  text/attribute extraction under the existing bounded rule contract. This
  closes D-72. Executable repository evidence is still blocked before CI step 1,
  so the story remains IN_REVIEW.

- **Security/accessibility/local-meetings batch implemented: S-06.02.02, S-06.02.05 and S-07.01.03 are IN_REVIEW.** The API is private by default with a closed bootstrap/signed-callback exception list, route-enumerating auth coverage and validation responses that do not echo secret request bodies. The frontend now has shared skip/focus/live-region/modal semantics plus repo-wide keyboard contracts and keyboard equivalents for pointer interactions. Meeting capture now mixes microphone + shared system/tab audio locally, records transient 30-second chunks in browser memory, permits capture only through a loopback backend + loopback browser Origin, freezes the declared transcription provider/model for the whole meeting, persists transcript/timing/provenance only, and registers meeting transcripts with encrypted backup and subject deletion. Review and close-out found and fixed D-65 through D-70 before owner testing. Focused suites are authored but are not claimed passing until executable evidence exists.

- **Second build-ahead batch implemented: S-03.02.05, S-02.02.02 and S-04.01.01 are IN_REVIEW.** Browser platform identity, pacing and default budgets now come from one validated packaged registry; Reddit is the data-only acceptance case. Every agent run now owns exactly one editable `PLAN.md`, read fresh before every model decision, with the exact plan version captured into the append-only trace. Companions are persisted transactional rows beside the existing ToolRegistry, with exact memory scopes, authenticated CRUD/context endpoints and execution-time tool-grant enforcement. Companion profile text is also registered with subject deletion. Focused suites are authored in `tests/test_browser_platform_registry.py`, `tests/test_agent_plan.py` and `tests/test_agent_companions.py`; owner/executable verification remains intentionally deferred, so none is marked DONE. Review found and fixed D-59 through D-64, including platform-control drift, unsafe JSON concurrency, privacy-store drift and backup-restore SQLite lifecycle errors.

- **S-05.01.02, S-05.01.03 and S-06.02.04 are implemented and in review.** Extraction packs are now validated JSON data over the existing Scrapling path; competitor teardown deterministically maps public structural/performance facts into existing video recipes and the existing human review queue without accepting copied media; privacy operations now use one authenticated inventory for subject access and confirmed, retry-safe deletion across CRM/discovery/delivery data, redacted mail recall, AI context and egress, crawler state, traces, tagged generated artifacts, and application-owned CSV queues/exports. Focused acceptance suites are authored in `tests/test_extraction_packs.py`, `tests/test_competitor_teardown.py`, and `tests/test_privacy.py`. They remain IN_REVIEW until executable test/verifier evidence and the owner's later acceptance pass are complete. Review also caught and fixed D-53 through D-55 before owner testing.

- **S-05.01.01 crawler frontier is implemented and awaiting executable CI evidence.**
  Public discovery now persists crawl state in SQLite, leases due URLs so
  concurrent workers do not duplicate claims, schedules recently changed pages
  sooner than stable pages, backs failures off, and routes every admitted URL
  through the existing public-web/session-gated safety policy. Review found
  and fixed `D-51`: separate crawler processes could claim different URLs on
  one host while keeping separate crawl-delay clocks. The frontier now stores
  a transactional per-host next-request slot and the existing safe fetchers
  reserve it before requests. Seven focused acceptance/concurrency tests are in
  `tests/test_crawler_frontier.py`. A 2026-09-23 CHECK-mode cold review also
  fixed D-71: a persisted URL rejected by the current policy could otherwise
  consume the claim window repeatedly and starve valid due URLs behind it. Repeated latest GitHub Actions push/PR runs still fail before
  creating workflow step 1, so the story remains IN_REVIEW
  rather than being falsely marked DONE.

- **S-07.01.04 report artifacts are implemented on the feature branch.** A
  verified agent trace can now become XLSX, PPTX or PDF without another model
  call. XLSX links each finding to the exact trace row and neutralises formula
  injection; PPTX carries provenance on every claim slide; PDF prints the
  existing escaped offline HTML report through installed Chromium. Broken
  provenance fails closed and a packaged `offsetx-artifacts` CLI exposes the
  flow. Focused tests are present; executable CI evidence is still pending.
- **DONE dependency history is now mechanically enforced** (`S-06.02.17`, closing `D-48`). The verifier rejects a DONE story whose declared upstream story is in any non-DONE column, names both stories and the upstream state, and still accepts a chain whose dependencies are all DONE.
- **Every DONE evidence command now enters one locked runner** (`S-06.02.08`, closing `D-10`). The board uses `uv run` consistently, the verifier rejects commands that bypass it even when tests are skipped, and clean-checkout setup documents both locked Python dependencies and frontend `npm ci` before the verifier.
- **Delivery failures were recorded instead of hidden.** `D-47` is dev-tooling-only: `npm audit --omit=dev` is clean while the full tree has four findings and is tracked by `S-06.02.16`. `D-48` tracks the missing DONE-dependency check under `S-06.02.17`. `D-49` records the rejected workflow-file push and the transport fix used to finish this story.

- **Per-run cost and latency budgets are now one enforceable contract**
  (`S-06.02.03`). Existing pre-emptive money ceilings are reused rather than
  duplicated. A caller can also supply `latency_ceiling_ms`; cumulative
  provider/browser `took_ms` is read from the existing append-only trace, is
  preserved across resume, and stops new work with `status=over_latency` once
  reached. Outcomes expose actual latency, ceiling, remaining headroom and any
  one-operation overrun. Zero remains uncapped and invalid ceilings fail before
  a run starts.
- **CI now gives the board verifier the environment it actually verifies**
  (`S-06.02.15`, closing `D-46`): full Git history for evidence-commit ancestry
  and frontend dependencies before DONE evidence is replayed. GitHub Actions
  run 393 passed the repaired pipeline end to end.

- **A test refers to a trace step by finding it, not by counting to it**
  (`S-06.02.14`, closing `D-37`). Five files named `step-000002` and meant "the
  read action". Adding any step earlier in a run shifts every id after it, so a
  story with nothing to do with provenance broke the provenance tests — twice,
  and both times the fix was to bump a number.
- **A scripted decision now cites what the run offered it**, which is what a
  real model does: the observation carries `step_id=step-000002` into the
  prompt and the model repeats it back. An answer says `CITE` and the broker
  double fills it in from the instructions it was just handed — immune to
  renumbering, and a closer imitation of the thing it stands in for.
- Assertions use `step_id_of(trace, "action")`. Artefact filenames encode the
  step index too, so `"0002.png"` was the same bug in another costume and is
  now the screenshot of the step the finding cites.
- Tests *of* the numbering keep their literals: that a trace with no ids gets
  them assigned in order, that `step-000002` follows `step-000001`. There the
  number is the subject rather than a way of pointing at something.
- Proven by doing it: a step inserted into `agent/run.py` shifts every id in
  every run, and all 49 tests across the five converted files still pass.

- **Every commit the board names is checked against the branch**
  (`S-06.02.12`). **Ancestry, not existence:** `git cat-file -e` succeeds for a
  dangling object, so a sha orphaned by `--amend` passes any check that only
  asks whether the commit is there — which is how two entries carried an
  orphaned `0be650d` for thirteen days without anyone noticing. A sha that is
  not an ancestor of `HEAD` now fails and names the entry; one that is no commit
  at all fails; and a repository with no git is noted rather than failed,
  because the board is still readable in a tarball.
- 48 recorded commits, all on the branch.

- **The verifier now checks readiness the way it already checks DONE**
  (`S-06.02.11`). It re-ran every `DONE` claim and never asked whether `READY`
  was true. A story in `READY` whose dependencies are not finished now fails the
  build; a dependency naming a story on no column of the board fails; and a
  story sitting in `BACKLOG` whose dependencies are all `DONE` is named in the
  summary as available to pull. It found one on its first run — `S-06.02.03`,
  which became pullable when `S-06.01.03` landed the day before.
- The dependency parser reads to `**Size:**` rather than to the first full stop,
  because **story ids contain periods** — a pattern of `[^.]*` parses
  `S-03.02.04` as `S-03`, and the first version of the audit script this
  replaces reported the exact opposite of the truth because of it. There is a
  test whose only job is that.
- **Fixed: the rule that an open question blocks `READY` had never fired once**
  (`D-44`). Every question in `OPEN_QUESTIONS.md` names the story it blocks in
  its *heading* — `*(blocks S-06.01.02)*` — and the parser handed the check only
  what came after the heading. Three open questions were blocking nothing. The
  board was still honest, but by luck rather than by the check.
- That is the third control this session that looked present and was not, after
  a spend cap fed a hardcoded zero (`D-35`) and a key event with no default
  action (`D-40`). `DEFECT_LOG.md`'s second pattern now says the thing they have
  in common: **for every control, ask when it last actually refused something.**

- **Concurrent runs share one browser safely** (`S-11.05.01`), the last story
  in E-11. Measured before building rather than read: of its three criteria one
  held and two did not, and both failures were one mistake wearing two hats —
  state that has to be shared across runs, held per run.
- **Fixed: N runs divided the per-host pace floor by N** (`D-42`). The gap
  between actions lived in a dictionary on each tab, so two runs on one host
  went twice as fast as the floor allowed. Measured at 2.00s where 5.00s was
  honest. `browser/pace.py` now holds one rhythm per browser session, and
  records a *deadline* per host rather than a last-seen time — so a run claims
  its slot before sleeping, and two runs arriving together are spaced instead of
  both being waved through.
- **Fixed: the budget ledger lost two thirds of its writes under concurrency**
  (`D-43`). The lock was per instance and the file was shared, so four runs
  taking 25 actions each left 33 of 100 in the ledger — making the real ceiling
  three times whatever the owner set. The lock is now keyed by the ledger file,
  so any number of instances over it serialise without anyone having to
  remember to share one.
- A sequential probe of both of those passed while both were broken. The tests
  are concurrent for that reason.
- **Known limit, measured and pinned:** the account ceiling can still be
  overshot by one action per concurrent run, because `S-03.02.04` deliberately
  checks before an action and records after it so a failed action costs nothing.
  That decision is not reversed here. Measured at 1, 2, 3, 5 and 8 runs, the
  overshoot was N-1 every time, and a test holds it there.

- **Enter goes through the same gate as the button beside it** (`S-11.03.03`,
  closing `D-25`). `check_action` was called exactly once in `browser/page.py`,
  inside `click`; `press` called it zero times. The fix is not a second copy of
  the check inside `press` — `click` and `press` now ask the *same* function, so
  the set of things that need a human and the set of things that get asked about
  are one set by construction. That is the defect log's pattern 3, solved the
  only way it stays solved.
- What Enter would activate is answered by the page, because the accessibility
  tree cannot say whether the focused field belongs to a form or what that
  form's submit control is called — and "Enter in the same form" is the
  criterion's own wording. It **fails closed**: if the page cannot be asked, it
  asks the owner.
- **Fixed: the agent's Enter key never did anything** (`D-40`). `press`
  dispatched a key event with no `text`, so Chrome raised it and performed no
  default action. Forms were never submitted. Found because the live check could
  not demonstrate the hole it was closing, and measured key by key rather than
  guessed — Tab and Backspace work either way, Enter only with the character it
  produces. A broken verb in a closed ten-verb vocabulary is a large fraction of
  what the agent can do, and it meant `D-25` was a hole nobody could fall
  through *yet*.
- **Fixed before shipping: the first gate would have interrupted typing**
  (`D-41`). A `<textarea>` inside a compose form is "in a form with a Send
  button", so pressing Enter for a new paragraph would have stopped the run.
  Enter in a textarea makes a newline in every browser there is; it cannot
  submit, so it is not gated.
- Only Enter is treated as able to activate anything. Tab moves, Escape closes,
  the arrows scroll — and none of them even ask the page, because a round trip
  per arrow key would make reading a feed absurd.

- **A visible, cancellable delay before anything consequential**
  (`S-02.02.04`). `browser/countdown.py` holds a sensitive click for five
  seconds — the number `policy.py` has specified since August — reporting the
  seconds left to whoever is watching, and anyone can stop it from any thread.
  Cancelled, nothing reaches the site and nothing is charged to the account.
- **A countdown, not a dialog, and the reason is in `policy.py`'s own words:**
  a confirm box trains people to click through it, because that is what confirm
  boxes are for. A countdown asks for nothing — you only act if you want to stop
  it — so the reflex has nowhere to land.
- **An unattended run cannot use one at all.** A countdown with nobody watching
  is the human gate deleted while still looking like it is there:
  `docs/architecture/AUTONOMOUS_BROWSING.md` says E-11 does not auto-confirm
  anything, and that rule is now in the code rather than only in the document.
  The existing refusal — stop the run and ask the owner — is unchanged for every
  caller that supplies neither a countdown nor a confirmation.
- **One countdown covers one action.** A spent one raises rather than passing a
  second click through, because "the owner watched this one elapse" must not
  become a token that waves through something they never saw.
- A harmless click never waits. A countdown on every link would make the agent
  unusable, and people switch off things that are unusable.

- **`S-08.01.05` is finally `DONE`** rather than `IN_REVIEW`. It had sat there
  since 2026-08-27 — not because anything was wrong with it, but because the
  environment of the day could not install a frontend dependency, so half its
  evidence could never be re-run. The dependency installs cleanly now: 2 Python
  controls and 11 dashboard tests, both halves green. The board has no stale
  rows.

- **A run now has a money ceiling, not only a step ceiling** (`S-11.01.04`).
  `run(..., spend_ceiling_usd=...)` stops the run with `status=over_budget`
  before the decision that would cross it. An agent left running overnight can
  no longer cost more than was agreed.
- **The check runs before the model is asked anything**, so the ceiling is never
  crossed rather than reported once it already has been. That also makes
  stopping free — which is what makes it safe to resume from. Whatever the run
  gathered before the limit is kept: a run that found three facts and stopped on
  the fourth has still found three facts.
- **The ceiling survives a resume.** It is recorded on `run_started` and
  re-applied by `resume()`, and the spend is read back off the trace — so a run
  killed and restarted ten times counts one allowance rather than ten. Without
  that the feature would be a speed bump: stop at the limit, resume, spend
  without bound. Raising it is `resume(spend_ceiling_usd=...)` and has to be
  done on purpose.
- **The next decision is predicted from the most expensive one so far, not the
  average.** A ceiling is a promise, and the average lags a trend — a run whose
  pages keep growing would walk past the line while the average still said there
  was room. Stopping early is recoverable; exceeding a limit the owner set is
  not.
- A projection that is already above the ceiling is said in `run_started`, not
  at the step it stops on. "This will not fit" is worth knowing before the first
  page loads.
- **Known limit, tested rather than discovered:** a model with no price list
  cannot have its first decision predicted, so that one goes through whatever
  the ceiling says; from the second on the run's own costs take over. Refusing
  every run on an unpriced model would make free and local models unusable, so
  the exposure is capped at one decision and a test keeps it there.

- **A run now says what it will cost before it starts, and what it did cost
  after** (`S-06.01.03`). The estimate goes into `run_started` beside the budget
  it was derived from, carries its own basis, and comes back on `RunOutcome`
  next to the actual — `estimate_error` is the difference, which is this
  story's own indicator.
- **Fixed: the daily spend cap could never be reached** (`D-35`). The owner can
  set a per-provider daily limit; the check for it is real, the usage bar
  displays it, and the line that recorded what a call cost passed a hardcoded
  `spend_usd=0.0`. Measured: a $1.00 cap, 5,000 calls, $0.0000 counted, nothing
  refused. Priced properly those same calls are $8.00 and the cap refuses at
  once. This was the only thing standing between an agent left running overnight
  and an unbounded bill.
- **Fixed: the provider tells us what each call used and we were discarding it**
  (`D-36`). Every major API returns a `usage` block; the adapter pulled the text
  out of the response and dropped the rest, and cost was then guessed by
  dividing characters by four. Captured now in `_post`, the one place every HTTP
  call passes through, so no adapter has to remember — and translated across the
  two naming conventions in use (`input_tokens`/`output_tokens` and
  `prompt_tokens`/`completion_tokens`).
- **Fixed: the price of a call was computed in three places** (`D-38`), one of
  which returned zero. `registry.price_tokens` is now the only implementation;
  `ModelEntry.price` is a convenience over it and `broker.measure` is the single
  funnel every caller uses. This is the defect log's pattern 3 — two things that
  must agree, drifting apart — in arithmetic rather than in a list.
- Every figure now says where it came from. `usage_source` is `provider` when it
  is the provider's own count, `estimated` when it was guessed, and `cache` when
  nothing was sent. "The bill was $2.40" and "we think the bill was $2.40" are
  different sentences, and the owner is entitled to know which one this is.
- A **failed** call is measured too. The provider bills for the tokens it read
  before giving up, and a ledger that counts only successes under-reports
  exactly when the owner most wants the number.
- The run report shows estimated-against-spent at the top, and the header figure
  is now labelled `spent` rather than `estimated` — they are two different
  numbers and must not share a word.

- **Added `DEFECT_LOG.md` and `DECISIONS.md`** (`S-06.02.13`), asked for by the
  owner. One table of every bug, security hole and broken connection found, in
  plain English, with the date it was found — and one of design calls where the
  obvious thing was *not* done, with what that cost. The reasons things broke
  were spread across commit messages, `RETRO.md` and `CHANGELOG.md`: fine for
  reading one story, useless for *has this happened before?*
- **Writing the 34 existing defects into one table made five patterns visible
  that no individual retro had shown.** The sharpest: the same defect has now
  been fixed three times under three names (`D-14`, `D-24`, `D-32`) — two lists
  that have to match each other drifting apart, silently. Also: the bug is
  usually in code that was already `DONE` and passing, and for anything that
  *detects* something, the false positives are where the real defects live.
- Both logs are enforced rather than encouraged. `scripts/verify_board.py` fails
  when a defect marked `open` names no backlog item that exists, when an id is
  used twice, when a row does not say what went wrong or when it was found, and
  when a decision names no cost. Nine tests, each proving its rule can go red —
  a checker that never fires is worse than none, because it launders a false
  claim into a green tick.
- `RETRO.md` keeps its job: three lines of process lesson per increment. It is
  not replaced, and the defect log is not a place for lessons.

- **A CAPTCHA, sign-in form or 2FA prompt now pauses the run and asks**
  (`S-11.03.01`). `agent/wall.py` reads the accessibility tree for something only
  a person can get past; the run ends `needs_human`, names what it found, and
  leaves the browser on that page. Before this, the agent did the only thing left
  to it — burned its budget clicking around a page it could never get past and
  reported `stuck`, which says something went wrong but not that *you* are the
  fix.
- **Nothing here solves, evades or fingerprints around a challenge, and nothing
  here will.** That was decided on 2026-09-06 and written up in `RETRO.md`:
  enforcement on these platforms is account termination rather than a 429, so
  the asset at risk is the one the owner spent months building. A test asserts
  the promise structurally — `wall.py` imports a snapshot and a regex engine and
  holds no browser, connection or network client, so there is nothing in it that
  could act even if a later edit wanted to.
- **The check runs before the model is asked anything**, so a locked door costs
  no decision and no budget: a paused run resumes with all of it. `needs_human`
  is deliberately absent from the set `resume()` treats as final — a run that
  stopped because a person has to do something is exactly the run that should
  carry on once they have. `human_gate` stays final, because there the question
  is whether a consequential action happens at all, which is not a thing you
  resume into.
- **This detector is allowed to stop a run, and `injection.py` is not.** The
  trade was re-argued rather than inherited. A wrong injection match costs one
  line in a trace; a wrong match here costs the owner a glance. So this one reads
  structure rather than prose — a password field is an *editable* node, which is
  what makes "Forgot password?" (a link) and "Show password" (a button) not
  count — and asks for corroboration before it speaks. Two rules were tightened
  after they fired on ordinary pages: `/auth\b` matched
  `/help/two-factor-authentication`, and second-factor language plus any text
  box made a help article about 2FA into a wall.
- `Snapshot.names` now carries the accessible names, so the two things that ask
  *what kind of page is this* — `identity.py` for signed-in state and
  `wall.py` for something in the way — read one definition instead of two.
- The run report explains itself at the top for any ending that is waiting on the
  owner, not only for ones that went wrong. `needs_confirmation` and `human_gate`
  had been stopping runs without saying why above the fold.

- **A run can now be watched while it happens** (`S-11.04.02`). `agent/watch.py`
  turns each recorded step into a `Progress` carrying the verb, the live page
  URL and the run's running cost, and `console()` prints one block per step and
  flushes it. `AgentRun.run(..., on_progress=...)` hangs the watcher on the
  trace for the duration of the run and takes it off again in a `finally`, so a
  watcher cannot outlive the run it was watching.
- The hook lives on `Trace`, not at each call site. The trace is already the one
  funnel every recorded event passes through, and there are forty of them — a
  watcher hung there cannot be forgotten when a forty-first is added. It fires
  *after* the disk write, so nothing reaches a watcher that a crash would then
  erase, and a watcher that throws is swallowed: somebody looking at a run must
  not be able to end it.
- `S-11.04.01` tells you what a run did once it is over. This is so a run heading
  for the wrong page at step 4 can be seen at step 4 rather than read about at
  step 40. It shows; it does not stop — interrupting is `S-02.02.03`, and was
  not smuggled in here.
- **The verb a watcher reports comes from the step's recorded signature, not
  from its prose.** A click records "clicked More", and `clicked` is not one of
  the ten verbs. `[signature=...]` was already written into every action step by
  `S-11.05.02` so a resumed run could tell what it had already done. The parser
  and the writer now live together in `browser/trace.py` as `signature_in` and
  `signature_mark`, beside the `Step` they describe, so the two cannot drift.
- **Fixed: a read answered from the run's memo recorded no signature.**
  `S-11.02.04` serves a second read of an already-read page without asking the
  page again, and that step was being written without the marker every other
  action step carries. It went unnoticed because nothing had needed the verb
  back until now; a watcher could not name the step, and a resumed run could not
  match it.

- **Every run now writes a report a person can read** (`S-11.04.01`).
  `agent/report.py` renders one self-contained HTML page into the run's own
  directory: each returned fact with its value, quote, source URL, timestamp,
  trace step and screenshot, then every step in order with its cost. Provenance
  has been bound to facts since `S-11.02.02`; it lived in a JSONL file and a
  directory of PNGs, which is the right way to store an audit trail and a
  hopeless way to read one.
- It is written from `_outcome`, the single funnel every ending passes through,
  so no exit quietly skips it — and a failure to render one is recorded rather
  than raised, because the outcome matters more than the page describing it.
- **The report renders attacker-controlled text, and that is what the tests are
  mostly about.** Every quote came off a web page; the injection excerpts came
  off a page actively trying to be interpreted as instructions. Everything
  page-derived is escaped, and the tests assert on the *tags a browser would
  parse* rather than on substrings — `"onerror=" not in page` is not a test,
  because escaped text legitimately contains those characters and is inert.
  Removing the escaping makes three tests fail.
- A screenshot filename that is not local to the run directory is dropped: the
  name comes off the trace, and a name walking out of the directory would turn
  the report into a way of reading the disk.
- Nothing is loaded from the network — no fonts, no scripts, no stylesheets — so
  it opens offline from `file://` and cannot phone anywhere. Mode `0600`, beside
  the evidence it describes.

- **A page that tries to give the agent orders is now reported** (`S-11.03.02`).
  `agent/injection.py` scans both what the model is shown — the page outline —
  and anything a `read` brings back, and writes an `injection_suspected` step
  naming which rules matched.
- **It changes the record, not the behaviour, and that is the design.**
  Containment is already structural: the model can only name one of ten verbs,
  cannot supply code, and cannot reach the CRM, so an instruction on a page has
  nothing to reach for. What was missing is that an attack left no mark at all —
  the run carried on correctly and nobody learned somebody had tried. A smoke
  alarm, not a fire door; the fire door was built first.
- The quote goes in the step's capture artefact, never in `detail`: page text
  does not belong in `trace.jsonl`.
- Every pattern was narrowed against real page text. A bare "you are now"
  flagged *"You are now viewing page 2 of 5"*; a bare "new role" flagged *"Our
  new role this quarter is Head of Growth"*; a bare "act as a" flagged *"We act
  as a broker for European fintech firms"*; and an unanchored send-to-address
  flagged *"Send us your CV at careers@acme.test"*. 12 attacks caught, 11 pieces
  of ordinary business text left alone.
- **Fixed an evasion before it shipped:** the patterns stay inside one sentence
  with `[^.\n]`, so a newline stopped them and an attack wrapped across three
  lines was missed entirely. Page text arrives full of line breaks, so that was
  not a hypothetical layout. Whitespace is now collapsed before matching.

- **A resumed run does not do again what it already did** (`S-11.05.02`). The
  pair to `S-11.01.03`: a resumed run re-decides from the **live page**, and the
  page does not remember that the message was already sent — the Send button is
  still sitting there looking unpressed. Nothing in the browser can say
  otherwise; only the trace can, so action steps now carry their signature and a
  resumed run reads them back.
- The guard covers `click` and `press`, the two verbs that can send without the
  URL changing, and **deliberately not `goto`** — navigating is how a resumed run
  gets back to where it was working, and blocking a repeat would make resuming
  useless. The cost is written down where the choice is made: a URL whose GET has
  a side effect is not protected here.
- It fires only across a resume point, never inside one continuous run, where
  the agent is entitled to click the same thing twice.
- Filed `S-11.03.03`: **`press` has no consequential-action gate.** Verified —
  `check_action` is called exactly once in `browser/page.py`, inside `click`, and
  `press` calls it zero times. Enter in a form is a submit, so the gate that
  stops the agent clicking Send does not stop it sending. Filed rather than fixed
  in flight because the fix belongs with the human-gate story.

- **A killed run resumes where it stopped** (`S-11.01.03`). Construct the agent
  with `Trace.open(root, run_id=...)` and call `resume()`: the goal, budget and
  schema come back off the trace, so the caller cannot get them wrong, and the
  facts already gathered come back with their provenance intact.
- **There is no checkpoint file.** The trace is append-only, written a step at a
  time with the handle opened per write, so a killed process leaves a complete
  record up to its last step — and `Trace.read` already said in its docstring
  that replaying it is what resuming is built on. A snapshot written every few
  steps has a failure mode this does not: the snapshot and the trace can
  disagree, and then the resumed run believes something that never happened.
- Accepted findings are now written to the trace as `kind="finding"` steps, with
  the finding as a **capture artefact rather than in `detail`** — a value may be
  20,000 characters and a quote 4,000 against a 4,000-character detail cap, so
  serialising into `detail` would have produced JSON that silently failed to
  parse on replay, losing the fact it was recording. The audit detail names the
  field and its size and never the value: harvested content stays out of the
  JSONL and lives only in the 0600 artefacts.
- A resumed run gets **the remaining budget, not a fresh one**, and comes back
  knowing what it already tried — so the recovery and progress detectors from
  `S-11.01.01` and `S-11.01.02` do not restart from nothing.
- Resuming a run that already ended is refused, and a fact whose artefact is
  missing is dropped rather than rebuilt without provenance.

- **A run that is busy and getting nowhere is stopped** (`S-11.01.02`).
  `S-11.01.01` catches the agent repeating one *failing* action; this catches the
  other shape, where every action succeeds and nothing is learned — bouncing
  between two pages, or clicking a working button forever. `looping` and
  `stalled` are separate statuses because they are separate problems, and both
  return the facts already gathered.
- One notion of progress serves both detectors: a step counts if it produced a
  **new fact**, reached a page the run has **not visited at all**, or performed
  an action it had **not performed before**.
- Two corrections that the story's own third criterion forced — *a false
  positive is worse than a wasted step*. **Unvisited, not merely different**:
  bouncing between two pages is a different URL every step, so "different from
  the last one" would have let the exact cycle through. And **the action
  clause**: filling in a form is a dozen successful steps on one page with no
  fact and no navigation, and stopping that would kill the runs that were
  working. Both are recorded in the backlog as clarifications.

- **A failed action is recovered from rather than repeated** (`S-11.01.01`).
  Before this a failure became an observation and the loop carried on, with
  nothing stopping the model choosing the same failing action until the budget
  ran out — and it does choose it again, because the refusal comes back as text,
  the next decision is made from the same page, and the same conclusion follows.
  The same verb with the same arguments is now spent after one failure, and the
  model is told so plainly.
- **Three failures in a row end the run as `stuck`.** A distinct status from
  `budget_exhausted` because the two ask different things of the owner: a run out
  of budget may just need a bigger one; a stuck run needs the goal or the page
  looked at. Facts already gathered are still returned.
- **A timeout is retried with backoff**, recorded in the trace as `kind="retry"`
  so a trace cannot be misread as the agent having tried three different things.
  `ActionRefused` is never retried: a stale handle or a refused domain is an
  *answer*, and asking again produces the same refusal having spent the wait.
- Scope corrected during the build: the story said "navigation timeout, 5xx".
  HTTP status is not observable through the ten verbs — a 500 still renders, so
  `goto` succeeds. Transient means timeout-shaped, and that is recorded in the
  backlog rather than left as a criterion the code silently does not meet.

- **A page is read once per run** (`S-11.02.04`), completing F-11.02. A run is
  capped at 50 steps, and a step spent re-reading a page the run already read is
  a step not spent finding anything — with the model paying for the same text
  twice on the way in. A repeated `read` is answered from the run's own memo and
  recorded in the trace as a reuse.
- Two URLs that differ only by **how somebody arrived** are one page: the
  fragment is dropped, the host lowercased, remaining parameters sorted, and the
  tracking parameters in `TRACKING_PARAMETERS` stripped. That list is
  deliberately short — `ref`, `id`, `page`, `q` and `source` are real parameters
  on real sites, and stripping them would merge pages that differ and then serve
  the wrong text. Under-deduplicating costs a page read; over-deduplicating
  returns a wrong answer, so the bias is one-directional on purpose.
- **Acting on a page forgets it.** A document can change while its URL does not
  — "load more", a filter, a tab — so `click`, `type`, `select`, `press`,
  `scroll` and `back` drop the memo for the page they acted on. `goto` does not
  need to: it changes the URL and lands on a different key.
- Only `read` is served from the memo. `goto` is never skipped, because the
  agent often needs to *be* on a page to act on it and silently not navigating
  would leave every following handle pointing at the wrong document.

- **Fixed a bare statement being rolled back with somebody else's failed
  request** (`S-06.02.09`). The lock added on 2026-09-08 made two transactions
  safe against each other but left this:

      thread A   BEGIN, INSERT 'holder', raise  -> ROLLBACK
      thread B   INSERT 'bystander'             -> reported success
      surviving rows: []

  B's write was destroyed by A's failure, and B was told it succeeded.
- **Root cause: the connection was not in autocommit.** Python's default
  `isolation_level` silently opens a transaction before any DML and leaves it
  open, so a bare INSERT was never bare — it began a transaction the next
  thread's `BEGIN` collided with, and whose fate a later `COMMIT` or `ROLLBACK`
  decided. `db/connection.py` has always opened `isolation_level=None` and
  documents that the stores were written against it; the Postgres backend has
  always behaved that way. SQLite was the odd one out, which made this a
  data-loss bug on one backend and not the other.
- Added `GuardedConnection`: the object all 155 call sites reach through now
  serialises every statement on the shared connection. Replacing the object
  rather than migrating the call sites is both the smaller change and the one
  with nowhere left to forget. What it does not cover is stated in its
  docstring — the lock is released before rows are fetched from a returned
  cursor, so a lazily-iterated `SELECT` can still span another transaction.
  That is a read seeing in-flight state, not a lost write.
- A test parses `outreach/` with `ast` and fails if any long-lived connection is
  assigned without the guard. `backup.py`'s short-lived, function-local
  connections are correctly excluded — the hazard is a connection stored on an
  object, because that is the one two threads reach at once.

- **BREAKING: off_CRM now requires authentication on every host, loopback
  included** (`S-06.02.10`). The middleware used to enforce login only when a
  token or demo login happened to be configured, so a default local install
  served every contact to anything that could reach the port — verified: every
  `/api/` route returned 200 unauthenticated. Loopback is not an exemption. An
  unauthenticated local API is readable by every other process and user on the
  machine, by a browser extension, and by any page that can rebind a hostname to
  127.0.0.1.
  - **This does not break a local install.** Starting through
    `run_offsetx_web.py` provisions a token at `<data_dir>/local_api_token` with
    mode `0600`, prints it once, and reuses it on every restart. Paste it into
    the web UI. An explicitly set `OFFSETX_LOCAL_API_TOKEN` or demo login is
    never overwritten.
  - Refusal happens at construction, so a misconfiguration is a startup error
    rather than a service quietly handing out data.
- **Added a `Host` allowlist** (`S-06.02.10`). DNS rebinding is what makes "it
  only listens on localhost" untrue: a page points a name it controls at
  127.0.0.1 and reaches the API with the browser's cooperation. CORS does not
  prevent the request — it only stops the attacker reading the reply — and a
  rebound name looks same-origin. Unknown hosts get 421, checked before the
  public-path exemption. Set `OFFSETX_ALLOWED_HOSTS` for a public deployment;
  loopback names work with no configuration.
- Fixed a CORS mismatch: `X-off-CRM-Token` was advertised while the server read
  `x-offsetx-token`, so a client that followed the advertisement was refused.
- Test fixtures that build an app now say `allow_unauthenticated=True`
  explicitly. A config that simply forgot a token used to be indistinguishable
  from one that meant it.

- **Fixed silent data loss under concurrent writes.** `OutreachStore` shares one
  `sqlite3` connection across threads (`check_same_thread=False`) and FastAPI
  runs 193 of its 206 handlers in a threadpool, so two requests genuinely arrive
  at once. `sqlite3.threadsafety` is 3, which serialises a single *statement*
  and does nothing for a transaction made of several. Reproduced with two
  threads writing forty rows each: one raised "cannot start a transaction within
  a transaction" and **forty of the eighty rows were gone**, because the second
  thread's commit and rollback acted on the first thread's open transaction.
  `transaction()` now holds a reentrant lock for its whole body, which is what
  `db/connection.py` has always done. 64 call sites depended on this, including
  `claim_next` — the email worker's exclusive claim.
- **Fixed unbounded memory growth in the login rate limiter.** Pruning emptied
  each client's deque and left the key behind, so the dict only ever grew.
  Measured at 50,000 retained keys with every window long expired; one IPv6 /64
  is a single residential allocation and 18 quintillion keys.
- **Fixed a username timing oracle in demo login.** `and` short-circuits, so a
  wrong username returned before the password was compared and the difference is
  measurable — which leaks which usernames are real and wastes the constant-time
  comparison underneath.
- Added `tests/test_security_audit.py`: 8 regressions covering all three.

- Specified **E-11 — the agent browses the open web alone and comes back with
  facts you can trust**: 6 features, 15 stories, R-76 to R-90.
  `docs/architecture/AUTONOMOUS_BROWSING.md` is the build manual and
  `docs/architecture/E11_HANDOFF_PROMPT.md` is the self-contained prompt for
  continuing it in a fresh session.
- The epic exists because `agent/run.py` returns `result: str`. A sentence
  cannot be validated, diffed, sourced field by field, or written to a CRM. The
  three stories that carry the epic replace it: a declared schema
  (`S-11.02.01`), provenance bound to every fact (`S-11.02.02`), and a claim the
  cited page does not support being dropped rather than returned
  (`S-11.02.03`).
- Delivered `S-11.02.01`, the structured-result spine for autonomous browsing.
  A run may now declare a closed list of required fields; off_CRM validates the
  model's `record` in deterministic code, drops and audits undeclared fields,
  reports `status=incomplete` with unfilled fields instead of guessing, and
  preserves the original free-text result when no schema is supplied. The
  acceptance suite includes a real-Chromium run that reads a local page through
  the production loop. Returned values are not copied into the decision trace
  before provenance exists; provenance remains `S-11.02.02` and claim
  verification remains `S-11.02.03`.
- Delivered `S-11.02.02`, binding every returned structured fact to evidence
  captured by off_CRM itself. Trace steps now have stable ids; read evidence is
  stored privately beside the append-only trace with a screenshot, and model
  output may name only a source step id plus its quote. URL, UTC capture time and
  screenshot filename are resolved from the host-owned trace rather than trusted
  from model text. An unresolvable source is refused, and facts saved on an
  earlier page survive later navigation through their immutable provenance. The
  public `record` remains a simple field-to-value mapping for CRM consumers;
  mechanical claim verification remains `S-11.02.03`.
- Delivered `S-11.02.03`, deterministic claim verification for source-bound
  browser findings. An observed value is returned only when its cited quote is
  present in off_CRM's host-owned capture and that quote itself supports the
  value after conservative Unicode, case and whitespace normalisation. Token
  boundaries and word order stay meaningful, so `42` does not match `420`, and
  immediate negation is not erased. Model confidence cannot override a failed
  check. Unsupported fields are dropped and traced; a missing span in a capture
  marked as cut is reported as inconclusive truncation rather than hallucination.
  Derived findings remain visibly `derived` and are accepted only when every
  declared input is already a verified observed finding; this story deliberately
  does not invent a universal arithmetic or summarisation language. The dedicated
  acceptance suite includes a real-Chromium page where a plausible confidence-1
  wrong number is refused.
- Added `PRODUCT_BACKLOG.md §3b`, superseding notes for shipped definitions.
  Shipped stories are **not** edited in place — an evidence block that describes
  something which never happened is worse than no record — so each amendment
  names the story that carries the new work instead.
- Added `S-06.02.08`: every evidence command should use one test runner. On
  2026-09-06 the board went red because some evidence used `uv run pytest`
  against an unsynced venv while the rest used `python -m pytest`, and it looked
  exactly like a code defect. A lie detector that cries wolf gets ignored.

- Added several accounts per platform, each with its own budget (`S-03.02.04`).
  An account is `linkedin:work`; the default account is named after the platform,
  so every connection record written before accounts existed keeps working with
  no migration step. `browser/budget.py` holds a per-account ceiling for the hour
  and the day, checked **before** the action and recorded after it, and the
  refusal says when the budget returns. The problem being solved is not rate
  limiting — a platform that decides you are a script closes the account rather
  than answering 429 — so the defaults sit below the observed thresholds and
  nothing raises them by itself.
- **Looking is free.** `read`, `screenshot` and `wait_for` cost no budget.
  Charging for observation pushes an agent towards acting without looking first,
  which is the behaviour that gets an account noticed.
- Fixed `press` skipping the pace gate entirely. It was the one interaction that
  never met the per-host floor, so Enter could be sent at machine speed on a host
  slowed everywhere else. Found while wiring budgets: the list of verbs that
  spend was not the list of verbs that were paced. `back` is now paced too.
- `signin.connect` and `signin.verify` take an `account` label, so a second
  account is reachable and not merely representable. No function in that path
  accepts a credential, and the test that reads every signature still holds.

- Added the bounded browser Run Loop (`S-02.02.01`). A run now accepts an owner goal plus a hard decision budget, repeatedly perceives the current page, sends each decision through the existing AI egress broker, validates the model response against the browser's fixed ten-verb action vocabulary, executes at most one browser action, and appends both decisions and actions to the existing audit trace. Logged-in page state defaults to `INTERNAL` data, planning requires a Tier A/B model and fails closed otherwise, page text is explicitly framed as untrusted data to resist prompt injection, and consequential actions stop at the existing human-confirmation boundary rather than self-approving. The trace records provider/model, token estimates and estimated model cost; exact provider-ledger reconciliation remains `S-06.01.03`.
- Added revoke-and-forget for browser platform sessions (`S-03.02.03`). Disconnect now validates that vaulted material belongs to the target platform, clears the platform's cookies and origin storage from Chromium, destroys the per-account vault envelope containing the wrapped account key, removes the public connection record, and appends the attempt/result to the existing append-only browser trace without logging any session value. Browser deletion failures fail safe: the encrypted vault and connection record are retained for retry rather than showing a false disconnected state. A real-Chromium acceptance test plants a persistent auth cookie and proves it is gone after revocation.
- Added the browser session vault (`S-03.02.02`). Successful platform logins are now captured into authenticated encrypted storage before the connection can be recorded as connected. Each workspace/platform account gets its own random data-encryption key; that key is wrapped by a master sourced from Windows DPAPI, macOS Keychain or Linux Secret Service, with an explicit scrypt passphrase fallback when an OS credential store is unavailable. The raw master key and passphrase are never stored beside vault data. Vault capture/restore returns metadata only and remains trusted host orchestration, not a browser-agent verb or model tool. The shared AI egress scanner now also refuses generic cookie/token/password fields and credential-shaped free text even under `full` provider policy. CI and the pre-push hook now run the board verifier inside the locked `uv` environment so its evidence subprocesses resolve the same tested Python environment.
- Added signing in to a platform inside the box (`S-03.02.01`).
  `browser/identity.py` declares the six platforms — LinkedIn, Instagram,
  Facebook, YouTube, X, TikTok — as the signals that mean signed-in and
  signed-out, and records per workspace which are connected. `browser/signin.py`
  opens the login page, waits, and reads back *whether it worked*. **No function
  in either module takes a password, a username or a token, and a test reads
  every public signature and fails the build if one ever does.** The person
  types their password into the browser; nothing about it crosses back.
- Refused a stale element handle instead of silently re-numbering against a
  newer page. `Page._resolve` used to re-capture when the cached snapshot had
  been dropped, so a handle taken *before* an action resolved against the tree
  *after* it — pointing at a different element rather than at nothing, and the
  action reported success. Found by typing into a password field: Chrome adds a
  "reveal password" control once one has content and every later handle shifts.
  `Page.snapshot()` no longer has a "use the cached one" flag, because that flag
  was the bug.
- Fixed `profile_is_locked` treating a leftover lock file as a running browser.
  A browser stopped by a signal leaves `SingletonLock` behind and nothing
  removes it, so a profile nobody held was refused for good — in the box, a
  login that persisted in the volume and became unreachable on the next restart.
  The lock records `hostname-pid` and is now interrogated: the pid on this host,
  the singleton socket when the hostname is a container id that no longer
  exists. `clear_stale_lock` removes a proven-dead lock before launch and
  touches nothing else.
- Made that stale-lock probe work on hardened hosts that deny AF_UNIX socket
  creation. A missing socket path is now proven stale without opening a socket;
  if the path exists but the host forbids the liveness probe, the profile stays
  locked rather than risking two browsers writing the same cookie database.
- `BrowserSession.close(quit_browser=True)` sends `Browser.close` before it
  signals. Chrome batches cookie-jar writes and flushes them on shutdown, so
  killing the browser could lose the login that had just been completed.

- Registered the shipped protected-email work under E-07 / F-08.01 with five
  vertical stories and R-61–R-71. Four core stories are DONE with rerunnable
  evidence; the operator dashboard remains IN_REVIEW until its frontend test is
  re-run in an environment with the locked npm dependencies.
- Fixed the deliverability send-window test so its queue time is derived from
  the run date instead of expiring after the hardcoded 2026-08-24 fixture.
- Added the browser box (`S-03.01.01`): `browser/box.py` composes the existing
  hardened `SandboxPolicy` with the network on and a Docker named volume for the
  browser profile, so no host path is mounted and the CRM databases and keys are
  absent from the container's filesystem entirely. The DevTools port is
  published to loopback only.
- Added `browser/guard.py`: the domain allow-list, enforced per request through
  the DevTools `Fetch` domain before Chrome dispatches anything. Deny-by-default
  when unattended, allow-with-policy when attended, and the list can only narrow
  — never widen past `browser/policy.py`. Attached automatically by
  `Page.start()`.
- `SandboxPolicy` gains a `network` field defaulting to `none`, and
  `validate_network` refuses anything but `none` and `bridge`. The workspace now
  supplies its own mounts, so two differently-shaped boxes share one flag list.
- Fixed a deadlock in the CDP client: event listeners were awaited by the read
  loop, so a listener that answered an event with a command waited on a reply
  only that loop could deliver. Listeners are scheduled now.
- Added `STATE_OF_THE_PRODUCT.md`, `DEMO.md`, `CONTINUE.md` and `RETRO.md`,
  completing the delivery-process artifact set. `DEMO.md` blocks are runnable
  and were each executed before being written down.
- Added F-01.05 (three stories, R-58 to R-60) for publishing to a real platform.
  The backlog had no story for the adapter that actually posts content, which is
  the reason the product exists — found on review and added under change control
  rather than silently.
- Added S-06.02.07: an answered question stops blocking READY, so recording a
  decision unblocks the board instead of deleting the question.

- Adopted an explicit delivery process: `PRODUCT_BACKLOG.md` (now 7 epics, 15
  features, 54 stories, 71 requirements with zero orphans), `BOARD.md` as the
  single source of truth with a WIP limit of 2, `OPEN_QUESTIONS.md`,
  `DEFINITION_OF_DONE.md` and `TRACEABILITY.md`.
- Added `scripts/verify_board.py` — a standard-library-only verifier that
  re-runs every DONE item's own evidence command, fails on orphan requirements,
  orphan stories, unresolvable evidence, WIP breaches, unescalated blocks and
  stubs inside a finished slice. Wired into CI and into a `pre-push` hook.
- Documented `docs/architecture/BROWSER_AGENT_BLUEPRINT.md`: how each Strawberry
  capability maps onto this codebase, and why a Chromium fork is replaced by CDP
  attach to the owner's own browser profile.

- Added an email deliverability subsystem with isolated traffic streams,
  permission evidence, global suppression, one-click unsubscribe, domain-auth
  checks, durable send jobs, rate/backoff state, an Amazon SES adapter, signed
  SNS feedback processing, seven-day authentication freshness, reply-aware job
  cancellation, health thresholds and automatic campaign pause.
- Added the Deliverability control-centre screen and the
  `offsetx-email-worker` production worker entry point.

- Rewrote the README around the complete local-first GTM workflow and labelled
  stable, beta, alpha and external-provider boundaries explicitly.
- Replaced real contact information in public sample and test data with
  synthetic records.
- Fixed the verified AI-run endpoint crash when `checks_suite` is supplied.
- Added a shared eval-suite path resolver and shipped the eval configuration in
  the Python package, guarded by source/package drift tests.
- Repaired the reproducible `uv --locked` installation and upgraded audited
  Python dependencies.
- Added critical Ruff checks and installed-CLI smoke tests to CI.
- Added Apache-2.0 and repository metadata to the Python package declaration.

## 0.12.0

- Added a self-contained AI module (`offsetx_apollo_builder/ai/`) with a single egress broker that every outbound provider call must pass through.
- Added a config-driven provider registry in `config/providers.yaml` covering 17 providers with jurisdiction, data-retention terms, rate limits, context window, cost and a verification date; adding a provider is now a config edit rather than a code change.
- Added four-level trust tiers derived from both jurisdiction and retention terms, with per-model provenance caps, default-deny for unlisted providers, and failover that never crosses a tier boundary.
- Added four data policies (strict, minimal, standard, full) with per-tier ceilings, and owner overrides that require a written reason and record who decided and when.
- Added allowlist payload construction that starts from an empty dict, replacing the previous strip-fields-from-an-object approach.
- Added a pre-flight scanner that blocks and raises on email addresses, owner domains, twelve credential shapes, mail headers, internal field names, environment variables and local paths.
- Added local quota accounting with per-minute, per-day and spend caps, and a usage display for providers with no usage endpoint.
- Added an egress log storing the exact payload of every call, with an inspector screen so the data guarantee can be verified rather than trusted.
- Added mailbox egress lockout for every provider by default, unlockable only with an exact typed phrase and still refused for restricted tiers.
- Added per-workspace AI settings and Fernet-encrypted per-workspace provider keys with an environment-variable fallback for server deployments.
- Fixed an AI chat path that sent raw conversation text to a provider with no data policy applied, contradicting the module's own docstring.
- Fixed a scanner defect where patterns ran against JSON-serialised text, silently disabling every line-anchored mail-header rule.
- Fixed two paths that reached an AI provider without the policy guard, in the drafts API and the outreach CLI; an AST test now fails the build if a third appears.
- Moved Gmail and AI providers out of Settings into a dedicated Connectors screen showing country, trust tier, retention terms and usage per provider.
- Removed the hardcoded TypeScript provider catalogue in favour of the backend registry.
- Added a model selector, task mode, Markdown/HTML export and optional dictation to the AI chat screen.
- Added three run modes the owner picks per task: one model, compare all models side by side, or let a trusted lead model plan the job into steps.
- Added a tier restriction on the planning role: only Highest and Default trust models may lead a plan, because deciding who does what means seeing the whole job. Restricted models can still be given steps.
- Added plan validation so a returned plan cannot widen its own reach beyond the data class the caller offered.
- Added a model strip showing every connected AI, its trust level and how close it is to its daily limit.
- Expanded release coverage to 158 Python tests and 6 frontend tests, including 30 security acceptance tests for the zero-access data architecture and 16 for the run modes.

## 0.11.0

- Added a complete sales-tracker CRM whose Kanban lead cards are the single source of truth for the lead log, metrics, commissions, leak alerts and forecast.
- Added seven drag-and-drop stages, mobile status controls, required Lost reasons, optimistic revision checks and an immutable lead event trail.
- Added setter activity, speed-to-lead, booking lag, schedule disposition, show-up and DQ visibility.
- Added closer offer and close rates, one-call/follow-up sales, average deal size, revenue per call and loss-reason reporting.
- Added deposit, cash, paid-in-full, refund/clawback, net revenue, goal and net commission calculations.
- Added red leak detection for booking lag over four days, untouched follow-ups at seven days and deposits unpaid at fourteen days.
- Added best, expected and worst end-of-month revenue/cash projections with historical, pipeline, manual and fallback assumption provenance.
- Added schema v6, dedicated sales APIs, responsive React views, audit tests and operating documentation.
- Expanded release coverage to 69 Python tests and 4 frontend tests.

## 0.10.0

- Added a guarded Crawl4AI 0.9.2 JavaScript-rendering adapter with fixed non-evasive settings, browser-route SSRF checks, robots.txt enforcement and no cookies, proxies, stealth or persistent profiles.
- Added a bounded prompt compiler for target counts, role focus, competitor expansion, social-handle collection and connector requirements.
- Added a persistent local research graph for people, companies, source pages, reference-only social profiles and approved/manual interaction evidence.
- Added an official-API/manual-import boundary for social interactions without exposing social OAuth sessions to AI providers.
- Added a visible Apollo rejection ledger with retry policy, automatic-repeat blocking and strict separation from the permanent accepted-contact exclusion ledger.
- Added CRM controls for crawler choice, research prompts, compiled plans, graph relationships and Apollo outcomes.
- Expanded release coverage to 63 Python tests and 3 frontend tests.

## 0.9.0

- Added guarded Scrapling parsing and public-web crawling with robots.txt, rate, redirect, size, content-type, domain allow-list and SSRF controls.
- Added persisted discovery runs and candidates with evidence, confidence, status and exclusion reasons.
- Added exclusion against `old_pois`, previous Apollo outputs and existing CRM contacts before review or enrichment.
- Added a React Lead Discovery screen with approval, rejection, Apollo queue and CRM-import controls.
- Added an explicit account boundary: no AI provider receives browser cookies or social-account credentials, and authenticated social scraping remains disabled.
- Expanded release coverage to 60 Python tests and 3 frontend tests.

## 0.8.0

- Added pre-send generation traces, exact bulk correction previews, re-audit, approval reset and per-draft not-before scheduling.
- Added campaign send windows, weekday controls, timezone enforcement and backwards-compatible all-day API defaults.
- Added provider data policies, optional redacted payload logging, persistent health state and priority, round-robin or parallel routing.
- Added a replaceable memory boundary with approved human corrections, de-identified outcome learning and local SQLite retrieval.
- Added provider-call observability and memory control APIs plus React control-centre surfaces.
- Added explicit experiment hypotheses, controls, minimum samples, Wilson intervals and lift reporting.
- Hardened Render writable storage and expanded release coverage to 56 Python tests and 3 frontend tests.

## 0.7.0

- Added a temporary single-user CRM login with signed HTTP-only sessions and login throttling.
- Added Render Blueprint configuration, automatic `PORT` handling, and a readiness health check.
- Added a dedicated responsive login screen and logout control.
- Documented disposable Render data and the hosted Gmail OAuth boundary.

## 0.6.0

- Added encrypted local AI provider profiles and secret storage.
- Added priority-ordered provider failover, response normalization and circuit breaking.
- Added reply-first campaign automation with daily caps and explicit Gmail activation.
- Added passphrase-encrypted local backup and verified restore.
- Added provider, automation and backup controls to the React Settings page.
- Expanded the release suite to 45 Python tests and 2 frontend tests.

## 0.5.0

- Added FastAPI local CRM API and React control centre.
- Added campaigns, contacts, drafts, queue, reply stop, exports and A/B reports.
- Added local SQLite schema, migrations, FTS expert library and event audit.
- Added strict OffsetX email expert and eight versioned A/B templates.
- Added OpenAI, Anthropic, compatible API and template-application adapters.
- Added Gmail OAuth and safe local outbox providers.
- Added daily limits, working-day scheduling, atomic send claims and idempotency.
- Added API token, upload, provider URL and spreadsheet export security controls.
- Preserved both Apollo search and existing-POI enrichment workflows.
- Expanded release suite to 38 Python tests and 2 frontend tests.
