## 2026-11-05 — A05 video workspace isolation: full isolated automated QA green

- Code/test source `246741b8663d56991d169af246dab77681f63648`, isolated Render `dep-dbm4lgrbc2fs738acn6g` completed all configured test stages (LIVE status to be separately confirmed). Focused A05 4 PASS; complete SQLite **3,036 PASS / 57 skipped / 44 warnings**, complete real disposable PostgreSQL **3,061 PASS / 101 skipped / 44 warnings**, focused PostgreSQL 215 PASS. Real Chromium desktop/mobile, frontend build/tests/audits, Ruff/security, 12× concurrency, structural board verifier PASS (`--skip-tests`, not historical evidence replay).
- This hardens the A05 cross-workspace video ownership boundary, not full CRM tenancy Q-27 or independent penetration/customer acceptance. Retain S-06.02.68 BACKLOG and S-06.02.23 IN_PROGRESS. No main/customer or real media deployment. Source `docs/evidence/2026-11-05-a05-video-workspace-isolation.md`.

## 2026-11-05 — A05 video workspace ownership: TDD and isolated QA in progress

- Working branch `develop`. During live audit S-06.02.23, new build-ahead S-06.02.68 found global video ID/list access ignoring already-stored workspace_id. TDD RED source d22d3a8 / isolated Render `dep-dbm4isu1egvs73bau35g`: **4 expected FAIL** (real cookie sessions, two workspaces, private project, render and audio).
- Fixed existing schema-free ownership boundary through VideoStore SQL workspace filtering, VideoEditorEngine own-record guards and protected direct downloads at `77307a8`, `9300330`, `de92a5a`; intermediate GREEN `dep-dbm4khbm8hqs73encvo0`: **3 PASS / 1 FAIL** because undo caught the owner refusal as a 409. Fixed error mapping at `a94aedb`, test extended at `246741b8663d56991d169af246dab77681f63648`; final isolated Render `dep-dbm4lgrbc2fs738acn6g` QA in progress.
- Source evidence `docs/evidence/2026-11-05-a05-video-workspace-isolation.md`, defect D-372, decision DD-148, requirement R-195. This does not migrate CRM Q-27, close A05, certify live penetration, or deploy main/customer application. Keep S-06.02.68 BACKLOG.

## 2026-11-05 — A24 final source-bound isolated QA LIVE

- Executable/test source `411770421133ea292153e68d9d0642cd1e198fc5`, isolated Render review `dep-dbm3oj8ae00c7389h7d0` **LIVE 2026-11-05 08:41:29 UTC** (14:11 IST). TDD RED (review `dep-dbm3nv9srm7s73f07bs0`) 4 expected fail/1 owner-path pass; GREEN A24 5 PASS on full app/session TestClient.
- Full SQLite `uv run pytest -q`: **3,032 PASS / 57 skipped / 44 warnings**. Full real disposable PostgreSQL `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`: **3,057 PASS / 101 skipped / 44 warnings**. Focused real PG **215 PASS**. Chromium desktop/mobile Contacts/Public Demo, A09/A18 browser checks, frontend npm tests/build/audits, Ruff, security gates, 12× SQLite concurrency and structural board verifier PASS (`--skip-tests` historical replay).
- Build-ahead S-06.02.67 stays BACKLOG and active S-06.02.23 IN_PROGRESS. Wider A24 retention, cross-store deletion after backup restoration/reindex, Q-27 tenancy, independent penetration, full-history verifier and customer/main release remain OPEN. No paid provider calls, real customer deletion, production or main service changes. Evidence `docs/evidence/2026-11-05-a24-privacy-owner-authorization.md`. Later commits since 4117704 change documentation only.

## 2026-11-05 — A24 owner-only privacy API security regression (initial RED/GREEN checkpoint)

- Source at start `c8f9bf7790c1731a0a985e34253443a830238f8f`, working branch `develop`. Existing `privacy.py` already implements a 12-store inventory, access, confirmed resumable deletion and nonpersonal receipts; do not misreport A24 as absent. Identified missing install-owner authorisation at all three destructive/read API routes and the confirmation phrase route.
- TDD RED test source `f808156` / review gate `4c97f56`, isolated Render `dep-dbm3nv9srm7s73f07bs0`: **4 expected failures, 1 passed**, using real FastAPI session logins with synthetic users and contacts.
- Fixed existing `api/app.py` routes via existing `require_install_owner` at `411770421133ea292153e68d9d0642cd1e198fc5`; no new role model, migration or provider call. GREEN A24 `uv run pytest -q tests/test_audit_a24_privacy_owner_authorization.py`: **5 passed / 1 warning** on isolated Render `dep-dbm3oj8ae00c7389h7d0` (step #27).
- Build-ahead story S-06.02.67 stays BACKLOG under active S-06.02.23 audit. Full-source SQLite/PostgreSQL/Chromium QA, end-to-end backup/retention/restoration deletion proof, Q-27 CRM tenancy, full-history verifier, independent penetration and customer release are still open. No main/customer deployment. Evidence: `docs/evidence/2026-11-05-a24-privacy-owner-authorization.md`.

## 2026-11-05 — A10 paid receipt safety: final exact-source isolated QA LIVE

- Repo `kunalwagh101/off_CRM` branch `develop`. Final executable/test source `822ffa8401d0d8ad1498a84e487fcd5f747b90a7`; isolated Render review `dep-dblrlb6i0phs7387c37g` confirmed **LIVE 2026-11-04 23:28:47 UTC**. Subsequent documentation commits did not change the executable/test source.
- RED source `1f4f9b9` 7 expected failures / 2 existing passes; fix `763a862` and `48e271`; synthetic test-classification error D-370 corrected in `8871aa7`. A10 expanded focused: **12 PASS, 1 early PostgreSQL-only skip**. Full SQLite Python **3,027 PASS / 57 skipped / 44 warnings**; full real disposable PostgreSQL **3,052 PASS / 101 skipped / 44 warnings**, including real A10 two-process USD reservation race; focused real PG **215 PASS**. Frontend build/tests/npm audit, Chromium desktop/mobile, Ruff/static/security gates, 12× concurrent SQLite writes and structural board verifier passed.
- S-06.02.66 remains BACKLOG (build-ahead against active S-06.02.23 audit), not DONE. Real provider invoice reconciliation, independent penetration, full-history evidence replay, customer acceptance and `main` release are OPEN. No production/paid model data used; rollback must preserve quota ledger. Evidence: `docs/evidence/2026-11-05-a10-paid-usage-integrity.md`.

## 2026-11-05 — A10 priced AI receipt integrity, TDD repair (full review pending)

- Active production audit S-06.02.23 next finding: A10. New build-ahead remediation S-06.02.66 with work order and acceptance. No other branch, customer/main deployment or schema change.
- RED test source `1f4f9b9`, isolated Render `dep-dblrg5h5efls73aj916g`: 7 expected failures, 2 passes. Confirmed all-zero token receipt was accepted as provider-confirmed free use and nonfinite token parsing could raise after provider I/O.
- GREEN implementation `763a862` and `48e271`: shared adapter/parser rejects invalid, all-zero, nonfinite or boolean receipts; broker cost measurement falls back to a positive labelled estimate without re-calling a provider or resetting quota. Focused A10 test `uv run pytest -q tests/test_ai_billing_integrity_a10.py` **9 passed** on source `48e271` / isolated Render `dep-dblrgs2jnfac73d9g7ug` (step #27). Subsequent source `839fc67` adds failure and real process/database concurrency cases; its review results are pending.
- This is A10 receipt handling, not a complete provider invoice reconciliation or independent penetration. Full PostgreSQL, SQLite, web/browser/security gates, full-history verifier and customer acceptance must be observed on final source before asserting review pass. No live provider used.

## 2026-11-05 — A05 isolated full Render review completed, LIVE

- Review `dep-dblr106i0phs7385jao0` on exact executable/test source `94fa650586ea0ca40178d47b473354dabb1abc67` reached LIVE 2026-11-04 22:44:20 UTC. New A05 real-API regressions: 3 PASS; full SQLite 3,015 PASS/56 skipped/44 warnings; full real disposable PostgreSQL 3,039 PASS/101 skipped/44 warnings, plus focused 215 PASS. Frontend tests/build, npm audits, Chromium desktop/mobile Contacts and Public Demo, A09/A18 browser security, Ruff, concurrent SQLite probes and structural board verifier PASS.
- Full-history board replay, independent penetration, per-user roles/CRM tenancy (Q-27), actual customer/provider acceptance and main deployment remain OPEN; this was isolated review QA only. S-06.02.23 stays IN_PROGRESS. Detailed source evidence `docs/evidence/2026-11-05-a05-workspace-permissions-recheck.md`.

## 2026-11-05 — A05 individual workspace permissions recheck (isolated API evidence)

- On `develop`, added three real FastAPI session tests in `tests/test_audit_a05_workspace_identity.py` (`ee14710`) and made them an early gate in `Dockerfile.review` (`94fa650`). No runtime application code, customer service, `main` or production data changed.
- Isolated Render review `dep-dblr106i0phs7385jao0` executed the exact source-bound command `uv run pytest -q tests/test_audit_a05_workspace_identity.py` with **3 PASS, 1 deprecation warning in 4.65s**. The tested paths are cross-workspace permission refusal against forged headers, owner-only user management, and disabled-session invalidation with an unaffected peer account.
- This is a partial A05 audit recheck under active S-06.02.23, **not** closure of the whole feature or independent penetration. Other access, role, CRM tenancy (Q-27), full-history board verification, live provider/customer release and remaining audit criteria remain open. Broader review stages and final deployment status require their own observed results.

## 2026-11-04 — A20 authenticated media: isolated review LIVE, release gates open

- Develop TDD RED `b4b2833` / review `dep-dblhbtu417fc738i5b5g`: 8 expected A20 failures/1 pass. First GREEN candidate `fdfee395` / `dep-dblhe1lg1s2s73ensrm0` failed on new URL-guard parser syntax. Corrected executable source `af434cfbc8c50bd7ba6a7c937595347b15b1761d` under review `dep-dblhej942hec73889ntg`.
- Confirmed on exact source: 19 frontend suites / 223 tests pass, production frontend build pass, npm production audit 0 vulnerabilities (2 moderate dev advisories), full SQLite 2,997 pass/56 skipped/44 warnings, full disposable PostgreSQL 3,021 pass/101 skipped/44 warnings, focused PostgreSQL 215 pass, auth integration stage 35 pass, targeted security/board verifier pass, Chromium Contacts and Public Demo desktop/mobile pass. Board verifier skipped historical command execution.
- The isolated review runner `dep-dblhej942hec73889ntg` is **LIVE** 2026-11-04 11:51:12 UTC on exact executable/test source af434cf. This proves automated review gates only. No customer service/main deploy, independent penetration, real token-only image/video browser acceptance or full-history verifier. Board S-06.02.63 IN_REVIEW and audit S-06.02.23 IN_PROGRESS.

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

## 2026-11-03 — S-06.02.23 audit A16 source check

Confirmed \`_send_job\` still creates its provider outside the catch that classifies failed and uncertain deliveries. Tracked D-363 and S-06.02.61 in BACKLOG with RED-first durable worker tests and explicit no-double-send controls. No execution/SES/penetration proof from this source review; audit IN_PROGRESS and no main/customer changes.

## 2026-11-03 — A11 source recheck under S-06.02.23

Current \`develop\` still has QuotaTracker check before EgressBroker provider transport, with record afterward; individual locks do not coordinate processes and local damaged state can reset counts. Logged D-362 and BACKLOG S-06.02.60 for atomic reservations and crash-safe recovery. This is source review, not live penetration evidence; audit stays IN_PROGRESS. A12/A13 restart regression source 6528060 entered isolated Render QA dep-dbl0abqjnfac73a521g0 with 9 targeted cache tests PASS; full QA was still running at this checkpoint. No main/customer changes.

## 2026-11-03 — F-06.02 A12/A13 response-cache integrity repair; RED confirmed, GREEN focused

Branch `develop`. Existing S-06.02.23 full September production audit remains IN_PROGRESS. Two independent remediation sub-stories S-06.02.58 and S-06.02.59 added and marked IN_REVIEW, with D-360 and D-361, separate work orders and audit status. TDD test-only `1593a42`, early QA gate `3e06faa` on isolated Render `dep-dbkrmik9v7es73f6gj1g` **FAILED all four as intended**: 42m/420m and approval negation wrongly reused old content; model/prompt partition was absent. Existing app was never deployed to customers.

Implementation `c55dca4` (`ai/cache.py`) and `0457dde` (`ai/broker.py`): exact factual matching, model/id/instruction/options partition digests and accurate egress context. Test correction `25f882c` removes two unsafe near-hit assumptions. Its isolated Render `dep-dbkrodt9fdbs73c5vik0` passed all 4 new cache-integrity tests in the initial gate; other review stages had not completed at this checkpoint. New broker integration tests committed in `80f5b3c` and early runner gate in `397b998`; those two were not in the initial GREEN image, so do not reuse the early result as acceptance for them. Complete SQLite/PostgreSQL/Chromium/board-structural gate, full-history verifier, independent penetration, real model/provider acceptance and production deployment still require verification on the final exact source. No schema migration or customer state change. Cache miss rate may increase intentionally; quota/price protections remain existing and must not be misrepresented as solved by these stories.

## 2026-11-03 — A09 S-06.02.57 isolated QA final, IN_REVIEW

Working branch develop, final tested code 065c31001ae9042d4bde7472aa8dcd1bcdd263ac. TDD RED: Render dep-dbkpkiek1f9s73dllh50 (dfe6b78) 4 FAILED; first GREEN patch dep-dbkpn83bc2fs73a1hljg (0fef11d) found D-359 five stale keyboard tests, full SQLite 5 FAILED / 2949 passed. Corrected legacy tests and model self-approval check in 065c310. Final isolated QA Render dep-dbkps0m7bikc73fil3vg **LIVE at 08:59:44 UTC**: 4 A09 focused and 34 legacy PASS, 4 real Chromium A09 PASS, full SQLite 2954 PASS/54 skip, disposable full PostgreSQL 2977 PASS/100 skip, focused PG 215 PASS, concurrency 12/12, frontend/build/audits, Ruff, existing Chromium desktop/mobile and A18 cases PASS. Structural board verifier --skip-tests PASS; full-history verifier replay not done. No main/customer deployment or external penetration certification. S-06.02.57 IN_REVIEW, audit A09 narrowed closure, S-06.02.23 IN_PROGRESS. Docs/evidence/2026-11-03-a09-enter-approval.md.

## 2026-11-03 — S-06.02.57 A09 fail-closed Enter approval (TDD RED proven, GREEN QA pending)

Selected a new A09 security repair while S-06.02.23 production audit remains IN_PROGRESS. Work-order/board e900eec, test-only dfe6b78. Render isolated RED dep-dbkpkiek1f9s73dllh50: 4 failed / 67 deselected in 2.17s because unapproved Enter reached a page. Source patch changes `Page.press` to require human approval whenever a focused Enter's intent cannot be proven consequential by the existing simple classifier; uses the shared approval gate and no new model verbs. Focused GREEN, real Chromium, full regression and disposable PG still pending, no DONE or customer/main release. See docs/evidence/2026-11-03-a09-enter-approval.md.

## 2026-11-03 — A21 QA review deployment LIVE

Render dep-dbkp0b7b9u1s738244k0 completed LIVE at 08:04:59 UTC on tested code e45469a7; 2950 SQLite / 2973 PostgreSQL PASS and all Docker Chromium/frontend checks passed. QA marker only, not customer/main deployment. S-06.02.56 remains IN_REVIEW for independent penetration, real provider acceptance, resource peak and full-history verifier. Evidence docs/evidence/2026-11-03-corrupt-images-a21.md.

## 2026-11-03 — A21 final isolated full QA green, IN_REVIEW

On corrected source e45469a, isolated Render dep-dbkp0b7b9u1s738244k0 passed A21 10, image/video 113, full SQLite 2950/50 skipped, full PostgreSQL 2973/96 skipped, focused PG 215, verifier unit 67, repeated concurrency 12/12, Ruff, frontend/audits, desktop/mobile Chromium and structural board verifier. Review image built, activation pending at record time. No customer/main deployment. Independent penetration, memory limits under hostile decompression, full-history verifier and real image-provider acceptance open; no DONE claim. See docs/evidence/2026-11-03-corrupt-images-a21.md.

## 2026-11-03 — A21 D-357 integration regression corrected; final QA open

Full SQLite on source `db02e52` in Render `dep-dbkopnp5efls73f7u9j0` found 3 FAILED/2946 PASSED/50 skipped: video import and still-image probe needed old header classification; valid blank PNG test fixture was no longer below the byte floor. Code `e45469a` restores header-only `image_size` for video and isolates strict `_fully_decode_image` to `run_gates`. TDD focused on exact revision in Render `dep-dbkp0b7b9u1s738244k0`: **10 A21 PASS, 113 image/video PASS**. The full regression, Chromium and PostgreSQL results remain pending; no release. Logged D-357, DD-136. See docs/evidence/2026-11-03-corrupt-images-a21.md.

## 2026-11-03 — A21 corrupt-image safety (IN_PROGRESS, full QA pending)

Test-first RED `84add30` on isolated Render `dep-dbkolbnb9u1s73819ns0`: 2 failed, 2 passed. Full-image verification implementation `7748855` targeted first Render GREEN 7 A21 passed; corrected false-positive binary fixtures D-356 at `9ba6cea` and expanded corpus/animation tests at `db02e52`. Exact-source isolated Render QA `dep-dbkopnp5efls73f7u9j0` pending. New safe limits are 16 MiB encoded, 8192 side and 16,777,216 pixels. Explicit already-locked Pillow dependency, no schema, provider calls, main/customer deploy. S-06.02.23 audit and F-06.02 are not completed. Evidence: docs/evidence/2026-11-03-corrupt-images-a21.md.

# BUILD_STATE.md

## 2026-11-03 — A18 final isolated Render QA (IN_REVIEW)

Source c1eefe2 / Render dep-dbkni7fb9u1s73fubjl0 LIVE at 06:22:32Z. TDD RED 15 fail on 00b1657; corrected A18 48 PASS, real Chromium 2 PASS, full SQLite 2940 PASS/50 skipped, full PostgreSQL 2963 PASS/96 skipped, focused PG 215 PASS, verifier unit 67 PASS, 12/12 concurrency, frontend/build/security audit and Chromium desktop/mobile PASS. Structural board check passed; full-history verification and independent live penetration did not run. S-06.02.55 moved IN_REVIEW; A18 closed only for tested numeric reproduction cases. F-11.02 original 4 sub-stories remain DONE. No main/customer deployment, migration or provider call. See docs/evidence/2026-11-03-numeric-claim-integrity.md.


## 2026-11-03 — F-11.02 source-bound numeric verification, RED confirmed

Working on owner-authorised A18 S-06.02.55 in existing F-11.02 (its original four sub-stories are marked DONE). New tests in `tests/test_agent_claim_verification.py` use the real `AgentRun` entry point, and `Dockerfile.review` makes them an early gate. Test-only commit `00b1657`, isolated Render `dep-dbkn8p59fdbs73bquspg`: **15 failed, 13 passed, 8 deselected**, expected RED. Fix to `agent/verify.py` guards numeric punctuation and separated signs, with further adversarial tests; final GREEN and full SQLite/PostgreSQL/Chromium/board verifier not yet observed at this checkpoint. Previous F-06.22 results apply to different source; do not reuse them as acceptance. The review image requires two real-Chromium signed/decimal A18 captures, structural board verification, and the expanded Unicode/locale cases. All results remain pending on this revision. S-06.02.23 audit remains IN_PROGRESS (WIP=2). No production deployment, external mail, provider usage, migration or schema change.


## 2026-11-03 — Continued S-06.02.23 production audit: two confirmed source gaps

The latest verified `develop` head before this documentation slice was `4dc461fd8b387d2bbd221aaee565d414f0f4241a`. No READY item exists; S-06.02.23 is the sole IN_PROGRESS audit, so new feature code was not pulled. The September audit index now identifies A18 and A21 as OPEN and links D-354/S-06.02.55 and D-355/S-06.02.56. Verification consists of comparing current source control paths with the audit's original adversarial cases; **no new executable pytest, browser, real provider, full-history verifier or Render gate was run for these gaps**. No code or production deployment changed. Next authorised work: continue per-finding audit checks, run full-history evidence verification, and only pull a remediation after READY criteria are met.


## 2026-11-02 — F-06.22 full independent isolated Render gate completed

Exact final tested source `f6de8a1b7b9fc1541489ec49e37654d5b5530f6a` on `develop`, isolated review `dep-dbk9o0gn74is73brdodg` **LIVE** at 14:37:46Z. RED a1c68e1 2 failed/4 passed for D-351 (legacy TAB/CR/LF) and D-352 (offset overflow risk); intermediate d931ba8 had 6 pass/1 failure solely due to D-353 test reading an integer EXPLAIN column. Final targeted **7 PASS**, full SQLite **2,892 PASS/48 skip**, full PostgreSQL **2,915 PASS/94 skip**, focused PostgreSQL **215 PASS**, verifier-unit **67 PASS**, concurrent API writes **12/12 PASS**, Chromium desktop/mobile Contacts and visitor demo PASS, frontend build/tests/audit and Ruff gates PASS. Synthetic 5,004-row SQLite duplicate scan **11.4ms**, planner SCAN+TEMP B-TREE; PostgreSQL 5,004-row EXPLAIN executed but actual time not logged. No new dependencies, schemas, provider calls, merges or production data change. F-06.22 remains IN_REVIEW, blocked by Q-27 tenant decision, independent live pen, full-history verifier, large-scale performance and manual production acceptance. See docs/evidence/2026-11-02-crm-duplicate-review.md.


## 2026-11-02 — F-06.22 TDD red and new security/performance gate

Committed to `develop` test `a1c68e1`, Render `dep-dbk9k6ijnfac73a0jpjg` 2 expected FAILED, 4 PASSED. Defects D-351/352: imported email with TAB/CR/LF missed by space-only trim; huge offset lacked upper bound. Fix code `d931ba8` uses matching SQL normalization in group, filter and contact preview, and rejects `offset > 1_000_000` at direct service and authenticated HTTP API. Added 5,004-row fixture for real SQL `EXPLAIN` on SQLite/PostgreSQL and permissive 20s regression alarm. Render GREEN review `dep-dbk9mpff3r2c7394ert0` started, not yet verified at this record. Q-27 workspace ownership, independently conducted penetration and production end-to-end acceptance remain release blockers. No main/customer deploy.


## 2026-11-02 — F-06.22 duplicate review, test-first backend delivery

Source on `develop`: `e86ff75` RED / `a0e9daf` GREEN. Four targeted tests failed on isolated Render `dep-dbk95sbbc2fs73epnd40` as expected; then all four passed on isolated Render `dep-dbk9797f3r2c73932q0g`, with other early API/permissions and verifier-unit suites passing. The complete isolated Render review finished LIVE at 2026-11-02T14:01:41Z on tested source `a0e9daf`: 2,889 SQLite pass/48 skipped; 2,912 PostgreSQL pass/94 skipped; focused PG 215 pass; verifier unit 67 pass; concurrency 12/12; Chromium desktop/mobile and frontend tests/build/audits pass. No production rollout; Q-27, independent penetration, large-data query-plan and full-history verifier open. Read-only authenticated `/api/v1/crm/duplicates` groups email collisions (case/trim), provides bounded paginated previews and never merges/writes contacts. No schema/data migration, customer deployment or main change. `BOARD.md` status IN_REVIEW; Q-27 tenancy, independent penetration, PostgreSQL-specific load/query-plan and full-history verifier remain release blockers. Full evidence `docs/evidence/2026-11-02-crm-duplicate-review.md`.

## 2026-11-02 — Verified AI-context migration review: isolated Render LIVE

Exact implementation/test source `12361049103a8913753899b34eba5ef2f18698e6`
on `develop`, isolated Render review `dep-dbk8on7f3r2c7391pn50`,
status **LIVE** at 2026-11-02T13:30:28Z. TDD migration gate 12 PASS /
1 PostgreSQL-only skip in SQLite stage; that PostgreSQL import case then
PASS in the real disposable PostgreSQL gate. Full SQLite 2885 PASS/48 skipped,
focused PostgreSQL 215 PASS, full PostgreSQL 2908 PASS/94 skipped, real
Chromium desktop/mobile contacts and visitor demo PASS, verifier-unit 67 PASS
and 12 repeated concurrency checks PASS. Full Docker build also enforced
frontend tests/build/audit and critical Ruff. Recorded in
`docs/evidence/2026-11-02-ai-context-import.md`.

The manual `offsetx-db import-context` can archive existing SQLite AI history
privately and import both tables transactionally (or deliberately skip), but
has **not** acted on customer files. The LIVE service is a QA marker only;
no main/customer deployment. Full-history board verifier, independent
security review, external encrypted backup/restore and other S-06.03.06
data-store migration are open; story remains BACKLOG under existing WIP policy.


## AI-context import: verified isolated Render review

2026-11-02: isolated Render review `dep-dbk8on7f3r2c7391pn50` on source `12361049103a8913753899b34eba5ef2f18698e6` finished LIVE at 2026-11-02T13:30:28Z. Full PostgreSQL 2,908 passed, 94 skipped, 44 warnings. Docker review completion requires SQLite, frontend, Chromium, PostgreSQL and focused early stages. No customer deployment. Full-history board verification, independent penetration and external backup restore not evidenced; S-06.03.06 stays BACKLOG.


## 2026-11-02 — S-06.03.06 historical AI-context migration

Source `12361049103a8913753899b34eba5ef2f18698e6` (branch develop) adds an
explicit `offsetx-db import-context` path to archive old SQLite AI task history
and either import both tables to the hosted store transactionally or skip it
without altering hosted records. Original SQLite files are removed only after
a verified private archive and successful destination transaction. Existing
hosted records are never silently merged. Changes remain production-inert
unless the owner runs the CLI.

TDD RED `ffd81e0`, isolated Render `dep-dbk8kfijnfac739tqm40` failed
collection as expected because the importer was absent. GREEN `2adfdcc`,
Render `dep-dbk8lnu7bikc739gfoq0`: 6 targeted import cases PASS. Security,
recovery, CLI and actual PostgreSQL tests were added; code hardened to close
SQLite connections and fail safely on corrupt sources at `1236104`. Final
isolated review `dep-dbk8on7f3r2c7391pn50`: 12 new import tests PASS,
1 PostgreSQL-only case skipped at the first SQLite gate; overall full review
results not yet certified at this checkpoint.

No real customer data was imported or skipped, no main/customer service
was deployed. The existing `S-06.02.23` board item remains IN_PROGRESS,
`S-06.03.06` remains BACKLOG and all other unhosted stores, external
encrypted backups, independent penetration, full-history board validation
and customer restore remain open.

## 2026-11-02 — S-06.03.06 PG counter portability repair

Full SQLite on `7fdc4f2`: 2,873 PASS/47 skipped/44 warnings. Focused PostgreSQL 215 PASS, Chromium contacts/visitor desktop/mobile PASS. Full PostgreSQL on that source had 1 FAIL, 2,894 PASS, 94 skipped: `test_hosted_context_on_disposable_postgres_after_reconnect` failed with PostgreSQL ambiguous `sends` column in counter UPSERT. Code `1ff58da` qualifies target table columns, checks both `sends` and `replies`, and adds an early real PostgreSQL test gate. Isolated Render `dep-dbk6enmtlv9c73f01ld0` is running, not yet accepted. Defect D-349 logged. Keep S-06.03.06 BACKLOG and do not infer customer deployment.


## 2026-11-02 — S-06.03.06 AI context readiness regression repair

Initial context source `ce82d33` failed full isolated SQLite QA `dep-dbk623cs728c73c78no0`: 3 failed / 2,870 passed / 47 skipped. Exact three hosted readiness cases returned `ai_context:OSError` because `production_runtime.runtime_health` probed the old ephemeral file instead of the configured database. Fix `7fdc4f2` selects `database_target` and adds targeted health assertions plus three previously failed tests before the full suite. Second Render review `dep-dbk66k0473hc73fo5bd0` is pending; no claim of green/full test acceptance yet. See docs/evidence/2026-11-02-hosted-ai-context.md.


## 2026-11-02 — S-06.03.06 hosted AI task context (partial)

New `tests/test_hosted_ai_context.py`, RED source `daa57cf`: 5 failed, PG-only case skipped; isolated Render `dep-dbk615oae00c73fue270`. Implemented `ContextLayer(database_target=...)` with versioned hosted PostgreSQL/SQLite schema, real application injection and safety guard for existing local data in code commit `ce82d33`. Early Render `dep-dbk623cs728c73c78no0`: 5 context tests PASS, PG-only skip; 6 timer tests and 14 migration tests PASS in focused gates. Broad QA not verified at this documentation point. This fixes a loss-on-restart path for new hosted installs only; historical local context needs an approved importer. F-06.03 remains open, no main/customer deploy. See docs/evidence/2026-11-02-hosted-ai-context.md.


## 2026-11-02 — S-06.03.06 legacy timer migration: pinned Render QA passed

On exact source `0232cf5e2d15493dd7538b10fcbc69e404609c47`, isolated review `dep-dbjri0utlv9c73e36570` is LIVE after all Docker QA gates at 2026-11-01T22:28:58Z. Targeted timer migration 14 PASS/1 PostgreSQL-only skip in SQLite stage; existing timer 6 PASS; readiness 7 PASS; full SQLite 2,868 PASS/46 skipped, 44 warnings; focused disposable PostgreSQL 215 PASS; full disposable PostgreSQL 2,889 PASS/94 skipped, 44 warnings (PostgreSQL migration case included); real Chromium Contacts and visitor demo desktop/mobile PASS; verifier unit 67 PASS, concurrency 12/12 PASS. Frontend and critical static gates passed. The QA marker is not the customer app. No customer/main deployment, real sends, independent penetration, full-history board command, or external backup/restore acceptance. S-06.03.06 and F-06.03 remain open; see docs/evidence/2026-11-02-timer-migration.md.


## 2026-11-02 — S-06.03.06 legacy timer configuration migration

Source `095c1a6` test-first: initial Render `dep-dbjrc2h42hec73ds2qr0` stopped with missing timer-import module, as expected. Code `3e9b87c`: nine focused migration tests and six timer-persistence regressions passed in isolated Render `dep-dbjrd3p42hec73ds5j40`; full suite not yet confirmed at this checkpoint. Security follow-up `fe93aad`: use an exclusive workspace lock instead of the shared lease; adds tests for concurrent workspace use, CLI positive path, and retry after database commit. **The security follow-up has not yet been tested on Render** at this checkpoint.

The `import-timers` command is operator-only and does not perform an actual migration or external send unless invoked by the install owner. It refuses conflicting stored settings, archives old JSON privately outside the ephemeral workspace, and imports timers disabled. See `docs/evidence/2026-11-02-timer-migration.md`; other F-06.03 stores, Q-29 backups and S-06.02.40 worker remain open. Board retains S-06.03.06 BACKLOG and audit S-06.02.23 IN_PROGRESS. No main/customer deploy.


## 2026-11-02 — F-06.03 / S-06.03.06 hosted timer configuration slice

**2026-11-02 final isolated QA:** On exact code/test commit `6166be7`, Render `dep-dbjqubh42hec73dr2bu0` reached LIVE at 2026-11-01T21:45:53Z; six S-06.03.06 timer tests, seven readiness tests, 2854 SQLite, 215 focused PostgreSQL, 2874 full PostgreSQL, 67 verifier-unit, 12 repeated concurrency and Chromium desktop/mobile passed. 45/94 suite skips recorded. This is the QA marker service, not a customer deploy; only the timer settings part of S-06.03.06 is implemented. The current develop documentation commits followed the pinned code test source, and the full-history board verifier, production restore and independent security review remain unresolved. See docs/evidence/2026-11-02-hosted-timer-settings.md.



**Code:** `ff40ea84843ea119be48b7d1eedbebac23f9e838`, corrected test `6166be72a618736e6bb0a60afcd6235bb45cee22`, branch `develop` only.
**TDD RED:** `dep-dbjqsn3bc2fs73dkcag0`, new `tests/test_hosted_timer_settings.py` 6 failed before feature code. **GREEN correction:** `dep-dbjqtnjbc2fs73dkedjg` 5 passed, 1 invalid fixture because settings omitted `secrets_key`; fixed fixture, no production guard relaxed. **Current Render review:** `dep-dbjqubh42hec73dr2bu0` pinned to 6166be7; six new tests and seven storage-readiness tests PASS. Full frontend, SQLite, PostgreSQL, Chromium and verifier outcome not yet seen at this checkpoint.

The email/content timer documents are stored in `offcrm_documents` for hosted installations. No temporary-file fallback, silent migration, independent worker or new external provider actions. All other stores in S-06.03.06 remain open and the story stays BACKLOG while S-06.02.23 is IN_PROGRESS; a linked work order records the partial implementation and complete remaining acceptance. No production or main deploy.


## 2026-11-02 — Production audit A06 session-revocation recheck (S-06.02.23)
**2026-11-02 final observed review gates:** For pinned A06 test source `37a6d2f`, Render `dep-dbjp60etlv9c73dt6sng`: auth 34 PASS; export/contact 19 PASS (A19/A23); full SQLite 2848 PASS/45 skipped; Chromium Contacts and visitor desktop/mobile PASS; focused disposable PostgreSQL 215 PASS; full disposable PostgreSQL 2868 PASS/94 skipped; verifier-unit 67 PASS; 12 concurrent API repetitions PASS. Docker image export succeeded in build logs. The deployment status was not yet independently confirmed LIVE at documentation time; no customer or main deployment. Audit table updated for A06/A19/A23 only; audit still IN_PROGRESS. See `docs/evidence/2026-11-02-a06-logout-recheck.md`.


New API-level regression `test_api_logout_revokes_only_current_session` added to `tests/test_api_auth.py` on `develop` at `37a6d2f`. Two distinct owner logins are issued; logout of the current login must revoke only its own cookie, leaving the other live login valid. Isolated Render review `dep-dbjp60etlv9c73dt6sng` launched on the exact test commit and was still building at the checkpoint; no test pass or production conclusion is claimed. See `docs/evidence/2026-11-02-a06-logout-recheck.md`. A06 and S-06.02.23 stay open until actual results and other findings are reviewed. The durable worker S-06.02.40 remains blocked on runtime, cost and durable-storage decisions. No customer/main deployment.


## 2026-11-01 — Corrective AI demo restoration (S-06.02.54)

The owner rejected the AI-disabled visitor demo. Restored existing broker-backed AI Chat/Compare/Plan/Image and provider setup, with AI-first public login. Each signed session gets its own AI workspace; logout removes that session's connected keys. Egress detail lookup now checks workspace (D-342). Visitor service LIVE on **39084d3**, deploy **dep-dbj8g5h42hec73ca9vd0**, at **2026-11-01T00:31:55Z**. Real HTTPS **37 checks passed**, including separate logins/chats/provider settings, no inherited keys, AI missing-provider errors, protected CRM writes and logout. Live browser verified AI and loaded provider Connect controls. Local 75 auth/AI/workspace checks and frontend 214/build passed. Final review **97e1e7b / dep-dbj8jdgu01pc73eomva0 LIVE at 2026-11-01T00:54:58Z**: **2847 SQLite**, **215 focused PostgreSQL**, **2867 full PostgreSQL**, verifier unit 67, desktop/mobile Chromium and all early gates passed. D-344/D-345 browser-harness selector/loading races were corrected and verified; the two earlier cancelled full PostgreSQL runs are not counted as passes. Runtime application files are identical between visitor source 39084d3 and reviewed source 97e1e7b.

The original off-crm service is now **LIVE on 97e1e7b**, deploy **dep-dbj8r2tg1s2s73f2oghg**, **2026-11-01T00:55:24Z**, replacing eb4c820. Backup login was declined; after the temporary-data reset risk was explained, the owner said “go ahead dont stopo”, recorded as authority to update this demo with the described reset. Its Render environment credentials were retained; no password guess, rotation or repeated login prompt. Original real HTTPS readiness, private-login configuration, no public credential advertisement, anonymous AI/CRM refusal and frontend asset match **PASS**. Private authenticated login was not exercised. No valid model key is configured on the visitor service; a real model response remains unverified. Existing Plan mode coordinates text jobs across models; arbitrary CRM actions from chat are not implemented by this repair. Branch docs now distinguish the intended Blueprint from the actual develop/manual-deploy services (D-346). See docs/evidence/2026-11-01-restore-demo-ai.md. **IN_REVIEW**, develop only; no main promotion or production-readiness claim.

## 2026-11-01 — Separate public visitor demo (S-06.02.53)

Owner requested a visible demo login separate from owner and QA accounts. Implemented opt-in sample-only installation, public-demo workspace, read-only server guard, visible/prefilled credentials and visitor banner. Existing CRM tenancy limits require a separate Render service, with fresh local sample-only storage and no hosted DB or private integrations. Visitor deployment LIVE at https://off-crm-public-demo.onrender.com/ on aaa0a59; real HTTPS login/read-only/logout/readiness verified. Local 49 Python and 213 frontend tests/build pass; Render core source 5e5039c full SQLite 2838 PASS and visitor Chromium desktop/mobile PASS. Render core PostgreSQL 2858 PASS, focused PostgreSQL 215 PASS; exact-latest startup covered by 4 local checks and real live service acceptance. Independent security/recovery review remains open. See docs/evidence/2026-11-01-public-visitor-demo.md. Private and QA services unchanged. IN_REVIEW, develop only.

## 2026-10-31 — cancel in-flight owner browser read

**Current feature slice:** F-06.01 / S-06.01.02 (IN_REVIEW). Added owner-only GET of the active chat browser run and DELETE cancellation by opaque run ID, with a process-local asyncio task registry. The POST browser-read task now returns `cancelled` after its runner has handled cancellation and the shared workspace browser lease is released in a finally block. Chat deletion, runtime restore and shutdown request cancellation. Registry has a close hook and a non-durable inventory entry; no schema migration or new AI provider path. No cross-process cancellation or live watch/cancel UI is claimed.

**Test-first Render:** RED `cf31c149515f598538f789f49afd4185c1d121c2`, isolated `dep-dbiugrm7bikc73dtnrr0`, **3 failed / 40 passed**. Candidate `fd8a73ae4a13eb1e04aaf2f59a970050883df806`, isolated `dep-dbiuigg473hc73ambq30`, targeted **44 passed**. Full SQLite **2828 passed / 45 skipped / 44 warnings**, Chromium desktop/mobile **PASS**, verifier unit **67 PASS**, focused disposable PostgreSQL **215 PASS**, full disposable PostgreSQL **2848 PASS / 94 skipped / 44 warnings**, Render isolated review `dep-dbiuigg473hc73ambq30` **LIVE** on exact tested source `fd8a73ae4a13eb1e04aaf2f59a970050883df806`, finished **2026-10-31T13:29:26.28068Z**. No `main` or production deployment. Source files: `agent/active_runs.py`, `api/app.py`, `db/inventory.py`, `tests/test_agent_permissions.py`. Evidence `docs/evidence/2026-10-31-chat-browser-cancellation.md`. Defect D-337; design DD-130.

**Still blocked for DONE:** real nested-Docker/browser/provider acceptance, cross-instance cancellation, owner progress/watch UI, cancellation during real browser IO, D-330 missing settings, upstream S-04.01.01, production network/durability, independent pen and full Git-history board verification. `develop` only; do not promote to `main`.


## 2026-10-31 — owner-initiated read-oriented chat browser run

**Tested application source candidate:** `3150fbb0de3a20e7f58f2ddcd59700353677fb0f` on `develop`; isolated review `dep-dbiskimc6qcc739ivrcg`. The user may now request a bounded browser reading task from an owned chat via an owner-only typed API. It uses a public HTTP(S) start URL, 1–5 decisions, strict live workspace policy, an existing short-lived chat-grant object, and shared workspace browser lease. The existing isolated `RoutineAgentExecutor` passes the chat grants into `AgentRun`, with read-only policy overlay; no new model provider path or durable store.

**TDD:** Render RED `f92a3e5`/`dep-dbisfo67bikc73dohamg`: **4 failed / 33 passed**. First GREEN `08c6380`: **37 targeted passed**. D-335 found unmonitored HTTP being treated as attended: RED `b6cc20e`/`dep-dbisj1ks728c7386u920`: **1 failed / 36 passed**; corrected social-site unattended restrictions in `3150fbb`. Final QA on `dep-dbiskimc6qcc739ivrcg`: **40 agent/permission targeted PASS**, runtime inventory **2 PASS**, verifier unit **67 PASS**, full SQLite **2824 PASS / 45 skipped / 44 warnings**, focused PostgreSQL **215 PASS**, full PostgreSQL **2844 PASS / 94 skipped / 44 warnings**, Chromium desktop/mobile PASS and Ruff clean. Isolated Render review `dep-dbiskimc6qcc739ivrcg` **LIVE** at 2026-10-31T11:18:11.991249Z, pinned to exact tested source `3150fbb`. No main/production deploy. Evidence: `docs/evidence/2026-10-31-read-only-chat-browser-run.md`. Design DD-129; defects D-335/D-336.

**Status IN_REVIEW, no main/production promotion:** no live watch/cancel screen, no demonstrated live isolated browser/provider session (the Render review uses synthetic tests), no proof of DNS rebinding isolation, no cross-process approval channel, upstream S-04.01.01 IN_REVIEW, D-330 still open, full-history verifier/independent penetration incomplete, and free Render trace durability insufficient. HTTP request is **read-oriented, not a true attended session**; it denies click/type/press/select and attended-only hosts, and GET navigation can still have effects.


## 2026-10-31 — F-06.01 authenticated chat isolation and owner-approved grants

**Current application candidate:** `8a35417505d6c03efc4f13ec79b2e3bdcc7bc304` on `develop`. Existing AI Copilot project/chat endpoints had omitted the current workspace, risking access to local-owner conversations (D-331); `send_message` lacked a pre-responder ownership guard. All API routes now pass the authenticated workspace; service reads and writes verify ownership before user content reaches the provider. The existing in-memory `ChatPermissionGrants` class now has explicit install-owner tool approval and close endpoints under the chat, a bounded workspace/chat registry and cleanup on delete, restart, runtime restore and shutdown (D-332). Grants cannot override `deny` and expire within one hour. No new persistent table, external AI provider or production change.

**Real Render RED:** source `43a5d14`, deploy `dep-dbiqkes9v7es738bb040`: **3 failed / 26 passed** (missing tenant-safe chat path and owner approval API). First implementation `d3978d8`, deploy `dep-dbiqlkajnfac73bc10vg`: **2 failed / 29 passed** due to test lifecycle misuse and approving an already-`allow` tool; both corrected in `a4e0855`. Targeted **31 passed** on Render `dep-dbiqmb142hec73b8c12g`; final source added shutdown-closure regression (**32 targeted passed** on `3588199`, Render `dep-dbiqn77b9u1s73c8pp80`). Source review then caught D-333: foreign workspace project DELETE falsely returned success. Corrected with truthful 404 on `d2d4788` and added a cross-workspace test. Review `dep-dbiqouvlk1mc73ffueb0` on `d2d4788` **FAILED full SQLite: 2 failed/2815 passed, 45 skipped**. Both failures exposed D-334: transient ChatPermissionRegistry absent from the storage inventory and runtime close order. Fixed on `8a35417`: registry has a no-argument close hook in RUNTIME_CLOSE_ORDER, is classified under NOT_STORES and both tests became early Docker QA gates. **Latest review:** exact source `8a354175`, QA `dep-dbiqtah42hec73b8v1sg`: targeted 33 agent/permission, 2 inventory/restore close, 67 verifier unit, **full SQLite 2817 passed / 45 skipped / 44 warnings**, Chromium desktop/mobile PASS. Full PostgreSQL and QA LIVE still pending at this checkpoint.

**Status: IN_REVIEW.** No attended browser run endpoint or owner approval UI yet, so the grant cannot currently be used through a customer-facing browser-agent chat. Upstream S-04.01.01 IN_REVIEW, D-330 missing-settings fail-open, independent pen test, full-history verifier and cross-process restart acceptance remain release blockers. Files: `agent/permissions.py`, `outreach/ai_chat.py`, `api/schemas.py`, `api/app.py`, `tests/test_agent_permissions.py`. Evidence: `docs/evidence/2026-10-31-attended-chat-permission-lifecycle.md`. No `main` or production deploy.


## 2026-10-31 — F-06.01 permission revocation while agent runs (D-327)

**Working branch:** `develop`, **initial application candidate:** `12b92516e02b1b73121ef31cbaf4672057c07114`. The scheduled browser agent formerly retained a run-start permission snapshot and the workspace settings reader could silently return empty/default-allow state when settings became corrupt. The fix adds a current-workspace strict permission reader, per-action refresh before any browser operation or cached read, a fail-closed refusal with a secret-safe error reference, and authenticated permission API protection against corrupt settings. No new model egress or database schema migration. Runtime files: `offsetx_apollo_builder/agent/run.py`, `agent/routines.py`, `ai/workspace.py`, `api/app.py`.

**Test-first RED confirmed** on isolated Render QA: `dep-dbifi0ui0phs739b7m80` for `a45716a` stopped with **2 failed/22 passed**. The first corrected source `12b9251` passed **25** targeted permissions tests, **2809 SQLite** and **2829 PostgreSQL** full tests, **215** focused PostgreSQL tests, 67 verifier unit tests and Chromium desktop/mobile; isolated deploy `dep-dbifjnrbc2fs73fbd6c0` reached **LIVE**. Following code review, D-328 uncovered the strict-read/lenient-write race: Render RED `dep-dbifr0afngtc73dig9l0` **1 failed/25 passed**. Fixed via `WorkspaceAISettingsStore.save(..., strict=True)` with strict document re-read inside the existing exclusive write lock; corrected code `09ded49a7c41c3b1402664e2fd83f3c64e53fd9c`, Render GREEN `dep-dbifrl2jnfac738ptqhg`: **26 targeted passed**, hosted-readiness 7 passed and Ruff clean. The next full SQLite run on `09ded49`, Render `dep-dbifrl2jnfac738ptqhg`, correctly **FAILED one existing concurrency test (2809 passed, 45 skipped)**: old `_document()` monkeypatch wrappers rejected the new `strict=False` argument (D-329). Corrected normal writes to call `_document()` unchanged while permission writes use `_document(strict=True)`. **Latest application candidate:** `e8200718c786b8d1fe2e9118b249aa405e087950`, Render review `dep-dbifv8942hec73f36l50`; targeted permission 26 passed, 12 concurrency repetitions and verifier 67 passed; final **full SQLite 2810 passed / 45 skipped / 44 warnings**, focused PostgreSQL **215 passed / 1 warning**, and Chromium Contacts **1280px and 390px PASS**. Final **full PostgreSQL 2830 passed / 94 skipped / 44 warnings** on source `e820071`; all tested unit, integration and Chromium gates green. Isolated review deployment `dep-dbifv8942hec73f36l50` **LIVE**, finished 2026-10-30T20:50:54.075282Z, on exact tested source `e820071`. **S-06.01.02 stays IN_REVIEW** because D-330, attended-chat grant lifecycle, independent penetration and full-history verifier remain open. No production or `main` change. Evidence: `docs/evidence/2026-10-31-agent-policy-revocation.md`, decisions DD-126/127, defects D-327/328/329.

**Status:** `S-06.01.02` remains **IN_REVIEW**, not DONE. Static review D-330: a completely missing settings document still appears as new-install default allow; decide fail-closed migration/presence marker before production. Unimplemented: attended chat owner grant and chat closure UI/API, full adapter coverage and independently observed pen test; upstream `S-04.01.01` remains IN_REVIEW; full-history `uv run python scripts/verify_board.py` not performed. No `main` or customer production deploy. Next step is complete verified Render full regression, then resolve chat/permissions lifecycle without widening the AI egress wall.


## 2026-10-30 — S-06.02.52 fully QA-tested on isolated Render review service

**Exact tested code:** `3e5058c1ac6dcd574534c78529a7c7e7e72bf3a8`. **Render QA:** `dep-dbhsifajnfac73c7bu4g` returned **live**, finished 2026-10-29T22:46:47.765324Z. Tests: operational-health 7, hosted-readiness 7, agent/permissions 22, full SQLite **2806 passed / 45 skipped / 44 warnings**, full disposable PostgreSQL **2826 passed / 94 skipped / 44 warnings**, focused PostgreSQL 215, concurrency 12/12, verifier unit tests 67, Ruff, existing Chromium Contacts desktop/mobile. The feature is owner-only read-only in-process scheduler diagnostics; `/health/ready` continues checking only required web components. **S-06.02.52 IN_REVIEW, A17 still OPEN**: no external email-worker heartbeat, measured queue age, configured alert dispatch, independent penetration/live worker interruption or full-history board verifier execution. No production/main change. Full source/test distinctions: `docs/evidence/2026-10-30-operational-health-qa.md`.


## 2026-10-30 — F-06.02 owner operational health, verified targeted tests

Story S-06.02.52 new owner-only `GET /api/v1/operations/health`, with healthy/disabled/degraded/unknown states for three in-process schedulers, all-workspace routine count, safe error references and no change to existing `/health/ready`. Render TDD RED on `3cf2c69`, `dep-dbhsga67bikc73fr5nrg`: **7 failed** missing route. Initial GREEN `b7d9bbd`, `dep-dbhsh9ks728c73cqtkl0`: **7 passed**. Final hardened source `3e5058c`, `dep-dbhsifajnfac73c7bu4g`: **7 targeted tests passed**, existing agent permissions 22 passed, storage readiness 7 passed and Ruff clean; full SQLite/PostgreSQL/Chromium still in progress at checkpoint. Separate external email-worker heartbeat, queue age, real alert delivery and independent penetration checks not implemented. S-06.02.52 stays **IN_REVIEW**; A17 not closed. Work order `docs/work-orders/S-06.02.52-operational-health.md` and evidence `docs/evidence/2026-10-30-operational-health-qa.md`. No `main` or production deployment.


## 2026-10-30 — F-06.01 permissions typed API fix verified; full regression rerun underway

The first complete SQLite run on `b27d6de`, Render `dep-dbhro9nlk1mc738sjic0`, found **1 FAILED, 2798 PASSED, 45 SKIPPED, 44 warnings**. The failure was the existing contract test `tests/test_api_auth.py::test_no_api_route_accepts_an_untyped_raw_dict_body`: the new `PUT /api/v1/agent-permissions` used `dict[str, Any]`. D-325 tracks it. Fixed on **`851d6de`** with `AgentPermissionUpdate(StrictModel)` in `api/schemas.py` and a fast review gate for the existing API contract. Actual Render review `dep-dbhrs0l9fdbs73af8e60` reports **22 permission/AgentRun tests passed**, **1 typed-body contract test passed**, **7 hosted storage tests passed**, Ruff passed. Full SQLite/PostgreSQL/Chromium stages were still pending when this note was authored. **Feature still IN_REVIEW**, not DONE or production released. Evidence: `docs/evidence/2026-10-30-agent-permissions-tdd.md`.


## 2026-10-30 — F-06.01 team permissions / S-06.01.02 implementation in review

Owner requested the next backend feature. Selected the existing F-06.01 / S-06.01.02 global, per-tool and chat-lifetime permissions. TDD RED: review deploy `dep-dbhrl9d9fdbs73aejus0` on `926144d`, targeted `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py` **failed at collection** because the permission module was absent; existing storage readiness 7 passed. Initial GREEN: same targeted gate **20 passed, 1 warning** on source `2e9872f`, review deploy `dep-dbhrmilg1s2s73fgfpbg`. Global and per-tool policy is stored in existing workspace AI settings (Neon/PostgreSQL supported); authenticated install token can update; normal member cannot. AgentRun checks before any browser action; unattended RoutineAgentExecutor loads the workspace policy. Found and closed initial routine `page.goto()` bypass in `27aad6e` with two new regression cases; final full QA still pending. ChatPermissionGrants are bounded, memory-only and expiring; **they are not yet wired to an authenticated attended chat grant/close API**, so S-06.01.02 remains **IN_REVIEW**. S-04.01.01 dependency also remains IN_REVIEW. No main or customer production change.


## 2026-10-30 — Initial storage-readiness QA marker LIVE; final 7-case security revision not tested

Render `dep-dbhr63ff3r2c73c62te0` confirmed **LIVE**, `finishedAt=2026-10-29T21:11:37.469348Z`, tested application source **`fc0a4cfa768ad24666477739dbae8c74e6e5df3d`**. That revision passed 5 new tests, 2,782 full SQLite, 2,802 full disposable PostgreSQL, 215 focused PostgreSQL, Chromium Contacts desktop/mobile and existing code/audit gates. The latest application source `d89bebb` adds two more security fixes/tests and has **not** had a successful Render run or deployment. Keep **S-06.03.08 IN_REVIEW** and do not call the latest SHA QA LIVE. Production/main untouched. Evidence: `docs/evidence/2026-10-30-hosted-storage-readiness-tdd.md`.


## 2026-10-30 — Initial F-06.03 API fully regression-tested, later security patch awaiting QA

Render source `fc0a4cfa768ad24666477739dbae8c74e6e5df3d`, deploy `dep-dbhr63ff3r2c73c62te0`, executed and passed **5 targeted owner readiness tests**, **2,782 full SQLite tests (45 skipped, 44 warnings)**, **2,802 full disposable PostgreSQL tests (94 skipped, 44 warnings)**, **215 targeted PostgreSQL tests**, desktop/mobile Chromium Contacts and Ruff checks. This is code/review evidence for **only that source**, not source `d89bebb` with the two later non-owner/root-mount regressions. The later source could not be re-deployed through the available execution interface. Both new security tests and the complete latest commit remain IN_REVIEW; no customer production claim. See `docs/evidence/2026-10-30-hosted-storage-readiness-tdd.md`.


## 2026-10-30 — F-06.03 storage-readiness QA checkpoint

Render TDD RED **5 failed/404**, implementation GREEN **5 passed**; initial implementation full SQLite **2,782 passed/45 skipped**, targeted PostgreSQL **215 passed** and Chromium desktop/mobile passed on `fc0a4cf`. Source `d89bebb` adds two tenant/mount regression tests **not yet run in Render**; final redeploy could not be triggered through available execution interface. Full PostgreSQL suite on initial GREEN source remained in progress at this checkpoint. **IN_REVIEW, not DONE**. See `docs/evidence/2026-10-30-hosted-storage-readiness-tdd.md`. Q-29/S-06.03.04 and S-06.03.06 production storage blockers remain.


## 2026-10-30 — Next feature F-06.03 storage-readiness report

Actual Render TDD RED: commit `0b96e38`, deploy `dep-dbhr4i2jnfac73an8ee0`: 5 failed because the endpoint returned 404. Initial GREEN: `fc0a4cf`, deploy `dep-dbhr63ff3r2c73c62te0`, same 5 targeted tests passed. New owner-only `GET /api/v1/storage/readiness` uses checked storage inventory, safe durability classifications and action codes; no URL/key/path contents or database writes. Additional non-owner workspace and OS-root mount tests at `d89bebb` require final QA. **IN_REVIEW**, not customer production: external encrypted backup S-06.03.04/Q-29 and remaining local stores S-06.03.06 are unresolved. Main unchanged.


## 2026-10-30 — ASGI video guard QA confirmed LIVE

Connected Render `get_deploy` returned **status `live`**, `finishedAt=2026-10-29T20:45:28.238135Z` for test-only review runner `dep-dbhqq2u1egvs7388ool0`, source `71fb99c554bf7d566ad6ad27e921c214c339884c`. Render logs also state "Your service is live" at 20:45:28Z. Tested source passed **2777 SQLite / 2797 PostgreSQL / 215 targeted PG**, Ruff, npm/frontend gates and Chromium checks; see `docs/evidence/2026-10-30-video-stream-qa.md`. **No customer/production deployment; A15 and S-06.02.51 remain IN_REVIEW for independent load, cross-process and security checks.**


## 2026-10-30 — S-06.02.51 video ASGI request guard QA tests passed

**Tested source:** `71fb99c554bf7d566ad6ad27e921c214c339884c`, Render review deploy `dep-dbhqq2u1egvs7388ool0` (isolated review service only). **2777 SQLite passed / 45 skipped**, **2797 disposable PostgreSQL passed / 94 skipped**, **215 focused PostgreSQL**, **12/12 concurrency repeats**, **67 verifier test cases**, **19 contact tests**, **Chromium desktop/mobile PASS**, Ruff clean. Frontend and npm audit gates passed in test image build. Eleven new video upload/body guard tests pass. See `docs/evidence/2026-10-30-video-stream-qa.md`. Render status was `build_in_progress` while export finished when documentation authored; check deployment state separately. **No customer production promotion.** S-06.02.51 remains IN_REVIEW: global concurrency, measured resource pressure, network penetration and multi-replica scenarios unresolved; A15 partially mitigated, not closed. D-321 moderate Vitest advisories remain.


## 2026-10-30 — Next F-06.02 security increment: A15 pre-parser upload guard

Owner selected next priority after QA of handler size limits: stop unbounded multipart parsing/spooling for video uploads. S-06.02.51 implements an ASGI request-body cap before FastAPI file parsing, private bounded temporary spool (256 KiB RAM before disk), per-worker max 2 concurrent uploads, 30-second inactive-sender timeout, deterministic cleanup, with both authenticated HTTP and low-level ASGI security tests. Independent local FastAPI prototype: initial test collection RED (guard absent), then 11 passed after code and test corrections. The prototype is not the actual off_CRM application; authoritative full-unit/integration/security/PostgreSQL results require Render QA. D-322. **IN_REVIEW pending deployment tests; A15 not marked closed.** No change to main/customer deployment.


## 2026-10-30 — Render QA status confirmed LIVE

Deploy `dep-dbhqd96i0phs73f1vfrg` on isolated QA review runner `srv-db86p4u89jmc73cehns0` returned **status `live`**, `finishedAt=2026-10-29T20:18:37.915787Z` (2026-10-30 IST), checked out application source `0c28d7c9be64d24a67f846142c5ff1dd56f50af3`. Actual Render logs say "Your service is live." **Not a production/customer application deploy.** Tested source and exact suite gates: `docs/evidence/2026-10-30-a15-video-upload-qa.md`. QA success does not close audit A15 or change IN_REVIEW to DONE.


## 2026-10-30 — A15 video upload endpoint fix verified on Render QA

**Actual source tested:** `0c28d7c9be64d24a67f846142c5ff1dd56f50af3`, isolated QA deploy `dep-dbhqd96i0phs73f1vfrg`. **2766 SQLite passed / 45 skipped**, **2786 PostgreSQL passed / 94 skipped**, **212 React passed**, **215 focused PostgreSQL passed**, **12/12 repeated concurrency runs passed**, **Chromium 1280px & 390px PASS**, **Ruff clean**. npm ci confirmed Vite 8.1.6 lockfile. Production npm audit 0 vulnerabilities; high-severity npm audit passed, but two **moderate** Vitest dev advisories remain (D-321). Six new A15 adversarial HTTP API tests passed in both Python suites. See `docs/evidence/2026-10-30-a15-video-upload-qa.md` for exact limits and warnings.

**A15 PARTIAL mitigation, not closed:** endpoint `UploadFile.read` now byte-bounded but multipart parser spooling, concurrent disk/resource quotas, interrupted transfers and a real video browser/penetration check still need work. `S-06.02.50` IN_REVIEW; `S-06.02.23` IN_PROGRESS. Full-history board verification and production release not performed. Docs-only handoff revisions after `0c28d7c` must not be described as new tested source.


## 2026-10-30 — QA blocked by a newly published Vite security advisory, patch authored

Actual isolated Render review build **dep-dbhqbjpsrm7s738gnbq0** on develop source `477a3fe` stopped at `npm audit --audit-level=high` (3 vulnerabilities, one high) on pinned vite@8.1.4. New docs/code revision pins patched vite@8.1.6 in both `frontend/package.json` and `frontend/package-lock.json`; exact integrity and compatible dependency references updated, no forced major upgrade. Rerun needed: `npm ci`, security audits, React tests/build, Python upload regressions and PostgreSQL suites. No claim that upload tests executed in the failed build. A15 and S-06.02.50 still IN_REVIEW; D-320 filed.


## 2026-10-30 — F-06.02 bounded video upload handlers in review

A15 video-media/render endpoints had unbounded file.read() despite configured max-upload setting. Under owner authorisation to start next existing feature, prepared S-06.02.50 with a bounded read helper, 6 new real-API/unit/security tests and D-319. Mechanism RED was locally reproduced in a minimal FastAPI endpoint: 4096 bytes returned 201 instead of 413; **this was not a run of the off_CRM app**. Tests in repository require Render execution before any PASS claim. **A15 remains open:** multipart parsing/spooling and concurrent disk/memory use are not capped by the endpoint read limit. Next: deploy QA review runner, inspect tests, fix, update status. No main or production changes.


## 2026-10-19 — FINAL RENDER STATUS: QA REVIEW MARKER LIVE

Review QA service `srv-db86p4u89jmc73cehns0` returned `status=live` for `dep-dbapefvbtjjs73834l00`, completed **2026-10-19T04:22:14Z**, using tested source `54864b0bb9172e73e2c1858aba06c82af1166277`. The Render build log confirms all executable Dockerfile.review test stages succeeded. **This is the QA marker, not the actual production off_CRM web service.** No production promotion, customer database changes, or `main` edits. Evidence: `docs/evidence/2026-10-19-render-qa-54864b0.md`. Full-history board verifier and independent user-path release gates remain open.


## QA verified — 2026-10-19 (source 54864b0b)

Render QA deploy `dep-dbapefvbtjjs73834l00` tested develop `54864b0bb9172e73e2c1858aba06c82af1166277`. **212 React tests**, Ruff clean, npm audits **0 vulnerabilities**, **2760 SQLite passed / 45 skipped / 44 warnings**, **2780 PostgreSQL passed / 94 skipped / 44 warnings**, **215 focused PostgreSQL passed**, **19 contact/export passed**, **3 security passed**, **67 verifier/CI tests passed**, **12/12 concurrent 40-create/restart repetitions passed**, Chromium Contacts **1280px PASS / 390px PASS**. Named commands, times, warnings, limits: `docs/evidence/2026-10-19-render-qa-54864b0.md`. All build test stages green; final Render status pending last check. The original 3 features remain IN_REVIEW, S-06.02.23 IN_PROGRESS and Q-27 unresolved. No real production app deployment or complete full-history board verifier. Subsequent documentation-only commit does not change the tested source.


## Active three-feature review hardening — 2026-10-19

Selected **existing IN_REVIEW product features**, not fresh builds: F-06.19 CRM Data Quality, F-06.20 Campaign Comparison and F-06.21 Follow-up Performance. F-06.19 adds Sales Tracker workspace-isolation regression; F-06.20 fixes inbound-before-outbound reply-rate inflation and adds chronology regression and clear UI wording (D-317); F-06.21 adds task-reopen/on-time regression. Detailed scope, isolated reproduction, exact commands and pending gates: `docs/evidence/2026-10-19-crm-operations-review-checkpoint.md`. No schema or provider changes.

**Test truth:** isolated SQLite old-vs-new SQL reproduction executed (old 1 / corrected 0). The new repository tests, browser acceptance, full Python/PostgreSQL, board verifier and redeployment are unverified at this checkpoint. Keep all three IN_REVIEW; preserve D-314/315/316 and owner question Q-27. Do not treat earlier 2026-10-16 Render LIVE as proof that the current source passed.


## Active review closure — 2026-10-16, real 503-contact and formula-safe XLSX checks

Two independent `IN_REVIEW` stories: S-06.02.41 and S-06.02.42. New test-only implementation:
- `tests/test_contacts_filters_export.py::test_503_persisted_contacts_can_be_reached_across_authenticated_pages` imports 503 persisted CRM contacts via the actual FastAPI/SQLite backend and reads six bounded authenticated pages including row 502, unique IDs, filter and unauthorised 401.
- `tests/test_spreadsheet_exports.py::test_every_report_tab_escapes_untrusted_rows_without_mutating_source` generates real CSV/XLSX and checks accepted, rejected, raw, decision and metadata report cells are safe text, with unchanged original input.
- Review runner `dep-db93t2mi0phs73c6msq0` executed the four relevant test files: **19 passed, 1 warning** (5.40s). Three fail-closed security tests passed, verifier/CI fixtures 67 passed. Evidence: `docs/evidence/2026-10-16-S-06.02.41-42-validation.md`; D-271/D-272 status notes updated; board still has 57 IN_REVIEW.
- **New D-314, not yet root-caused:** the same full SQLite run finished **2755 passed, 1 failed, 45 skipped**. One of 40 concurrent campaign creates returned HTTP **404**, not 201, during WP1 durability/restart test `tests/test_wp1_recovery_edges.py::test_concurrent_api_writes_are_all_durable_after_restart`. No conclusion yet about lost rows. Full QA build FAILED. This cannot be waived based on the 19 green targeted tests.
- Current QA rerun `dep-db941vm7bikc73dk5e5g` adds detailed failed-response reporting and 12 independent executions of that concurrency test before the full suite. The review-only Dockerfile also now attempts actual synthetic Chromium Contacts UI import/page/search with `scripts/live/review_contacts_browser.py`. Neither rerun nor Chromium acceptance is a pass until its build log finishes. Original customer service remains untouched; disposable loopback server/database only.
- Remaining S-06.02.41 gate: full Chrome/keyboard/screen-reader/edit/shrinking-page and independent review; remaining S-06.02.42 gate: offline Excel/LibreOffice opening and independent spreadsheet security review; CI full-history Git evidence blocked. Work only on `develop`.

---

## Latest verification update — 2026-10-15, fail-closed security regression

`develop` committed a high-severity fix **D-313** discovered during S-06.02.21 cold review: a missing request-context principal inherited installation-owner authority when reading linked products. Reproduced RED in Render `dep-db8cjmajnfac73f52o2g`. Fixed `_CALLER_WORKSPACE` to default deny and wrapped explicitly authorised content timers in a resettable scoped owner context; manual runs still require `require_install_owner`. Decisions `DD-121`. Linked-product GTM compatibility tests assert both deny-without-context and allow-with-an-explicit-timer-context. Full evidence: `docs/evidence/S-06.02.21-security-review-2026-10-15.md`.

**Verified green review runner:** `dep-db8cnnou01pc73fb3d8g` on `76bc929240192120e7506a80f60039d15548e9f5`: focused security/GTM **3 passed**, verifier/CI fixture **67 passed**, full SQLite **2754 passed / 45 skipped**, full real disposable PostgreSQL 17 CRM **2774 passed / 94 skipped**, dedicated PostgreSQL storage suite **215 passed**, separate two-instance PostgreSQL logout revocation **1 passed**. Full review image built and reached LIVE. npm audits already clean (0 production, 0 dev), 212 frontend tests passed, frontend production build passed on prior frontend-compatible revision.

**Separate QA web app** `srv-db86h3gm7kps73d8ud1g` was triggered for updated `develop` at `dep-db8cttm89jmc73d2ip00`; Render confirmed LIVE at source commit `fff73e1`: Uvicorn application startup complete and HEAD /, GET / both 200; direct `/health/ready` response and browser workflows not independently fetched. The original production service and `main` are untouched.

**Open:** GitHub Actions quality/postgres jobs still fail at runner allocation with 0 steps (run `38738223007`); authentic full-history board verifier remains unexecuted. Owner decisions/recovery, browser acceptance, independent security review and remaining story-specific criteria prevent promotion. Board remains **70 DONE, 57 IN_REVIEW, 16 BACKLOG, 6 BLOCKED, 1 IN_PROGRESS**, as recorded in `docs/evidence/2026-10-15-pending-80-item-register.md`.

---


## QA review checkpoint — 2026-10-15 (latest test evidence)

**Branch:** `develop` only. The official board holds **57 IN_REVIEW** (18 product features + 39 stories), 16 BACKLOG, 6 BLOCKED, 1 IN_PROGRESS, 70 DONE (150 total). Do not silently move status from green unit tests. Prioritised 57-item order, exact per-story test mapping and blockers: `docs/evidence/2026-10-15-pending-80-item-register.md`. Live review logs: https://dashboard.render.com/web/srv-db86p4u89jmc73cehns0.

**S-06.02.16 registry security blocker repaired:** after reproducing npm dev audit 5 advisories (2 high, 3 moderate), a networked npm lockfile regeneration installed Vitest 4.1.11 and upgraded nanoid, postcss and source-map-js. Matching `frontend/package.json` and lockfile committed. Render review deploy `dep-db8akqs9v7es73877d9g` ran clean `npm ci`, **212/212 Vitest passed**, production build passed, production `npm audit --omit=dev --audit-level=low` and dev `npm audit --audit-level=high` both returned **0 vulnerabilities**.

**S-06.02.20 board/CI checks:** review Dockerfile includes real Git executable and `.github` workflow files but excludes `.git` and secrets. Real shallow/full Git-fixture and workflow contract tests: `uv run pytest -q tests/test_ci_verifier_environment.py tests/test_verify_board.py` = **67 passed** (19.38 s). Original private repository commit ancestry cannot be certified in this Docker build because `.git` is excluded. A full-history authenticated checkout and CI runner remain required.

**Latest complete Python regression:** `uv run pytest -q` ran in isolated QA Build, **2,752 passed, 44 skipped, 44 warnings in 245.52 s**, zero failures, superseding the historical 72-failure baseline. The review runner reached **live**; original application service unchanged.

**PostgreSQL verification:** separate build `dep-db8aoopsrm7s73e0j1eg` adds a disposable local PostgreSQL test server, runs dedicated database cases and full suite with `OFF_CRM_TEST_CRM_ON_POSTGRES=1`. Do not record outcomes until build completes. Separate QA app `srv-db86h3gm7kps73d8ud1g` was manually triggered to deploy current `develop` after the clean SQLite build; no production app deploy was requested.

**Remaining release gates:** real hosted PostgreSQL migration/recovery and backups, live Chromium accessibility/network egress, external providers/recordings, explicit Q-27 customer tenancy boundaries, historical Git ancestry and GitHub Actions running, plus per-feature DoD/independent acceptance. Never use a test runner marker endpoint as a substitute for real app feature testing.

---

Working record for the off_CRM AI orchestration module. Read **this file** to
recover context between sessions rather than re-reading the codebase.

Then read **`docs/architecture/CAMPAIGN_TYPES.md`** before designing anything
new. The product is a CRM *with an AI layer that runs the campaigns itself*, and
email is one campaign kind of several. Nothing built from here may assume email.

Last updated: 2026-10-09
Branch: `develop` — the one working branch. Every line of work was merged or
ported into it on 2026-09-23; `docs/BRANCHING.md` says what came from where.
The 45 old branches are still on GitHub until the owner runs
`scripts/archive_old_branches.sh` — this session was refused (HTTP 403).
Tests (2026-10-03, on `develop` at `S-06.03.03` DONE): with
`OFF_CRM_TEST_POSTGRES_URL` on a real PostgreSQL 16, **2681 Python passed,
0 failed**, 1 skipped (a sandbox image); without the URL the PostgreSQL-only
tests skip. With `OFF_CRM_TEST_CRM_ON_POSTGRES=1` as well, the **whole suite
runs with the CRM on PostgreSQL: 2612 passed, 0 failed**, 70 skipped — tests
about SQLite itself or about a CRM file, each with its reason, and one sandbox
image (`tests/conftest.py`). CI has a `postgres` job for both, not yet run:
the runners are down (`S-06.02.18`). The whole suite last ran on a real Python 3.10 on
2026-09-24 (2404 passed); it has not been re-run on 3.10 since. Ruff gate
clean. Frontend **175 passed** and a clean production build. Board verifier
OK with every DONE story's evidence command re-run (2026-09-28).

**Newest: screens open at their top** (`S-06.02.25`, IN_REVIEW; checks passed
below). The CRM in the hosted database (`S-06.03.03`, DONE; next in
`F-06.03`: `S-06.03.04` backups, `S-06.03.07` filed by its review). Before it, the GTM engine,
Phase 1 and 2 (`E-12`) — section 3's first entry.
Read `docs/architecture/GTM_ENGINE.md` before touching `offsetx_apollo_builder/gtm/`.

The video editor is built: `offsetx_apollo_builder/video/` plus
`frontend/src/video/` and the **Video editor** screen. Read
`docs/architecture/VIDEO_EDITOR.md` before touching either resolver — there are
two implementations of one rule and a conformance fixture holding them together.
`docs/architecture/CAPCUT_FEATURE_MAP.md` is the feature inventory it was cut
from, and it now carries a **status column and a scoreboard**: 61 of its 162
rows built, 18 partly, 52% of the reachable rows touched.
`tests/test_capcut_scoreboard.py` recomputes those counts from the table, so the
summary cannot drift from what it summarises. Auto-captions is the first AI row
wired: `docs/architecture/AUTO_CAPTIONS.md`, and read its section on audio
before adding any other feature that sends bytes rather than text.

The long-standing `test_discovery.py::test_scrapling_parser…` failure was never
a code defect: `scrapling` is declared in `pyproject.toml` but omitted from
`requirements.txt`, so any environment installed from the latter lacked it. The
session-start hook installs via `uv sync --extra dev` and the test passes.



## 2026-10-09 — Five-feature programme, develop only

Owner selected F-06.02 reliability, F-06.03 hosted recovery, F-04.01 agent team,
F-06.01 team operations and F-12.02 GTM strategy. The concrete story queue and
upstream/owner/access gates are in `docs/DEVELOP_NEXT_WORK.md`. No branches or
worktrees were created; the old main-based work remains archived/stashed and
was not applied. Current scan base is develop `4b80d7c`.

S-06.02.38 traceable errors was committed and pushed to develop as `d3099f1`.
It is IN_REVIEW, code review clear. API/CLI/job
references, safe lifecycle protocol messages, bounded local logs, fresh cycle
scopes, workspace metadata and visible Settings/Posting status are implemented.
D-243–D-253 record the review findings and resolutions. The independent reviewer
ended with no remaining code finding. The exact ledger is
`docs/evidence/S-06.02.38-validation.md`; this is not DONE or a deployed release.

Locked dev/email/postgres extras installed. Use UV_CACHE_DIR=/tmp/off-crm-uv-cache
and UV_TOOL_DIR=/tmp/off-crm-uv-tools (home directories read-only); frontend cache
/tmp/off-crm-npm-cache. Baseline: 2569 passed, 22 failed, 22 skipped (21 Chromium
sandbox, one uvx cache fixed by override). Broad final regression run: 2612 passed,
21 Chromium failures, 22 skipped. Subsequent final affected run: 314 passed,
14 PostgreSQL skips, covering the last routine/safe-summary fixes. Frontend:
175 passed; production build passed with its existing large-chunk advisory.
Ruff and structural board checks passed. Whole-board run: 70 commands, 42
passed; Chromium environment prevents a green full-board gate. No sandbox or
test was disabled. Raw logs are copied to /workspace/artifacts/S-06.02.38.

Current real HTTP-process injected failure: status 500, one matching safe
record, local workspace. Earlier installed offsetx-db failure: exit 2, one
matching reference, password absent. Actual previous-revision process rollback
had readiness 200 and preserved the disposable CRM row/log bytes. No live
provider, PostgreSQL database, Render retention, deployment or CI pass claimed.

Owner authorised commit/push only to develop. Preserve the main-based archive
and stash. Continue the selected programme from the queue and actual board;
prepare the next independent READY slice and keep upstream/owner/access gates
open. Ending a task or a usage reset does not automatically resume work.

### Current slice — S-12.02.06 posting, IN_REVIEW

Apply declares a disabled posting/image pair with the plan's own rate. Owner
Start, workspace-scoped review/skip, transactional next-slot scheduling,
authenticated image/video previews and safe per-pair pace decisions are built.
D-254–D-265 record independent review fixes; final review has no remaining
concrete finding. Baseline affected tests 79 passed; final affected tests
145 passed. Frontend 181 passed and build passed (existing chunk advisory).
Broad pre-legacy-fix run: 2641 passed, 21 baseline Chromium failures, 22 skips;
latest broad result: 2643 passed, 21 Chromium failures, 22 skips. See
docs/evidence/S-12.02.06-validation.md.
The final affected run covers quarantine-result visibility after broad started.
Ruff and structural board checks passed. Browser/generated-media/live-social
and green full-board gates remain open; this is not DONE or a deployed release.

The owner requested a local run. App runs in the **cloud workspace** using
/tmp/off-crm-progress-server.py on loopback port 8766, serving frontend/dist.
Isolated data: /workspace/runtime/off-crm-progress; auth-token is private and
must never be printed, copied into artifacts, or committed. Real HTTP readiness
and frontend returned 200; rules plan applied disabled, Start enabled its pair,
manual caption approved/scheduled/published to the real local outbox, skipped
row never published. No model/social service used. Current-process restart
preserved the plan and published/skipped statuses. Plain archived d3099f1 source
also read a stopped-data copy and served its rebuilt frontend. Its process is
stopped; current app stays running. Automation is disabled after verification.
Raw safe results/logs: /workspace/artifacts/S-12.02.06. No laptop installation,
public preview, real browser walk, hosted restore or deployment is claimed.

Continue the five-feature programme from docs/DEVELOP_NEXT_WORK.md. Only
reliability logging and this posting slice have implementation/review evidence
from this session; do not claim the remaining large features are completed.

## 2026-10-04 — Screen navigation keeps its top in view (`S-06.02.25`)

Frontend implementation and independent review complete.
Pushed to `develop` at `815c72bbc7affdef29b2c288e4d7494a836ea292`; no `main` promotion.
Navigation focuses main without browser scrolling, then explicitly opens the
screen at scroll 0.
The main area's scroll margin matches the 68px desktop / 60px phone top bar.
No campaign store, screen component, API, database schema or credential setting
changed. Late campaign warnings stayed in view without adding another scroll
on background failures (`DD-79`). `D-137` is fixed.

Evidence this session: baseline and final full Python suites both **2570
passed, 43 skipped**, no PostgreSQL server configured; frontend **175 passed**,
production build passed; accessibility **12 passed**; egress wall **42 passed**;
Ruff passed. Real Chromium 153 through `run_offsetx_web.py` and the actual API
passed **32 checks** on Settings, Contacts, AI and Product at 1280x900 and
390x900: healthy navigation, delayed/existing campaign warnings, initial
failure recovery and preserved campaign-load gates. The full warning and
screen title are visible; long forms/chat panels may extend below the viewport,
but their beginning and first header/action are visible. Browser output and
the reusable launcher are linked from the work order.

Independent review corrected the browser selectors, render waits and disposable
launcher's inherited hosted-key configuration. It found an older skip-link
route defect (`D-239`), reproduced and filed as `S-06.02.37`; no additional
feature was absorbed. Whole-board evidence verification re-ran all 70 existing
DONE commands: **70 passed**. Historical commit ancestry was not checked because
the exact source snapshot has no local Git history. The story remains IN_REVIEW
for the full-checkout history and develop CI gates.
The baseline GitHub quality job also fails three older tests because it omits
the PostgreSQL driver; its separate postgres job passes (`D-241`, filed against
`S-06.02.19`). This is
work for `develop`; it is not a `main` promotion or a verified hosted release.
Existing blocked work remains on the board.

## 2026-10-03 — `F-06.03` phase 2: the CRM outlives the disk (`S-06.03.03`)

**DONE** (2026-10-03). Tasks a–i built, walked in a browser, reviewed in a
fresh context and pushed to `develop`; not deployed. The work
order, `docs/work-orders/S-06.03.03-crm-hosted.md`, holds every task's numbers.

**What it does.** With `OFFSETX_DATABASE_URL` set, the CRM — every one of its
31 tables — is in that database, for the web app and every tool
(`data_paths.crm_target`: a `--db` given, then the URL, then
`OFFSETX_OUTREACH_DB`). `outreach/store.py` runs the same SQL on both backends
and knows which it has only at opening, in transactions, at its first schema
and for search's index. A local CRM file holding the owner's rows stops a
hosted start until `offsetx-db import-crm --yes` or `--skip` (`DD-74`).
`offsetx-db copy-crm` copies a whole CRM either way: empty destination only,
one transaction, the source read at one moment and never written.

**How it is proved.** `tests/conftest.py` runs the whole suite with every CRM
on PostgreSQL (`OFF_CRM_TEST_CRM_ON_POSTGRES=1`); a test about SQLite itself is
marked `crm_sqlite_only` with its reason, and where its property also holds on
PostgreSQL, `tests/test_crm_hosted.py` proves it on both. Live: the real server
on PostgreSQL 16 kept a campaign through its data folder being deleted; a CRM
the app's own engine wrote (9,442 rows) went to PostgreSQL and back with every
value equal.

**The fresh-context review** (task i) found 11 defects, `D-227` to `D-237`.
The worst: once any tool had started on the database, the owner's local CRM
could no longer be imported, and only the web app refused to start while it
was left behind. Ten fixed test-first; one filed as `S-06.03.07` (installs
sharing one database). Walking that worst one with the real commands found
`D-238`, fixed. New decisions `DD-75` to `DD-78`; `DD-75` corrects `DD-73`:
accented letters fold on PostgreSQL only.

**Found and fixed on the way:** the email worker failed on PostgreSQL at
every send-window deferral (`D-221`); a closed connection reopened itself
(`D-222`, older); `copy-log` printed its URL's password (`D-225`, older); a
PostgreSQL URL as the CRM's path became a file named after it (`D-217`). The
work order's list of modules touching the CRM was built by text search and
missed one (`D-220`); the exact list came from tracing every statement.

**Not done, and where it goes:** backups of the hosted database
(`S-06.03.04`); production refusing a half-hosted install (`S-06.03.05`); the
stores with no decided home (`S-06.03.06`); expert search on PostgreSQL is
unranked — no full-text index there. A copy over the network to a hosted
database, and the CRM's load on Neon's compute hours, are unmeasured.

## 2026-10-02 — `F-06.03` phases 0 and 1: keys, settings and logins outlive the disk

**DONE on 2026-10-02:** `S-06.03.01` (the inventory of every store,
`db/inventory.py`, `offsetx-db inventory`, the table in `HOSTED_STORAGE.md`)
and `S-06.03.02`. With `OFFSETX_DATABASE_URL` and `OFFSETX_SECRETS_KEY` set,
provider keys (encrypted with that key, never stored), each workspace's AI
settings, limits and trust, the usage counters, workspace logins and the egress
log live in the database. With neither set, nothing changed.

**The owner's word, 2026-10-02:** not only Neon — Render's PostgreSQL too — and
build so the install can move to a PostgreSQL on AWS or Azure later (`DD-66`
amended, `DD-70`). The code names no host. Checked that day: Render's free
database is deleted with its data after 30 days plus 14 days' grace and has no
backups, so the free recommendation is Neon.

**Proof, not just tests:** a real app process (`run_offsetx_web.py`) on a real
PostgreSQL 16 was configured in headless Chromium — a key with the 200-a-day
and $5 presets, a trust raise with its reason, a colleague's login, a logged
call — then stopped and its data folder deleted. A new process on an empty
folder with the same two settings showed all of it, and the colleague signed
in. A different key, and no key, each stopped the start with a sentence. The
database held no plain-text key.

**Found and fixed on the way:** a PostgreSQL store never reopened a dropped
connection, so every hosted store would have failed after Neon's first
five-minute sleep (`D-199`, high); daily limits restarted at every spin-down
(`D-198`, high); privacy requests could not reach hosted logins (`D-200`); the
eval tool split the egress log (`D-201`); "encrypted on this machine" stopped
being true (`D-202`); unsubscribe links died at every restart on Render
(`D-203`); `.env.example` still offered provider-key variables (`D-204`).

**The fresh-context review of `646c593`** found ten defects, six medium, none
critical — the key core was sound. All fixed test-first (`D-206` to `D-215`):
a non-URL connection string became a local file (now refused); a billed answer
could be lost to a counter read (counters are read before a call, and counting
never fails it); a silently dropped flow hung the store (network keepalives,
about 15 seconds); signed-in browsers got a bare 500 in an outage (the
middleware answers the sentence); switching on beside a folder with data hid
it (refused until `offsetx-db import-local --yes` or `--skip`); a database
error read as the provider failing (passed through untouched). One more, older,
turned up under load: two connections opening a new SQLite file together
(`D-216`). A live outage — PostgreSQL stopped under a signed-in browser, then
started — showed the sentence and recovered with no restart. The fixes were
checked by tests, the reviewer's own reproductions and browser walks, not by a
second review.

**Read before touching storage:** `db/hosted.py` (documents, the key check),
`db/schema.py` (a version per store, forward-only, under a lock),
`db/connection.py` (reopen before a statement, never re-send one, never swap
inside a transaction). `S-06.03.06` is filed for the stores the inventory found
with no phase.

## 2026-09-25 — live bugs fixed; the owner's keys, limits, trust and storage decisions; two reviews

**Fixed from the live app** (each test-first, walked in a real browser):
NVIDIA's reasoning model refused every call (`D-147`); Render deploys timed
out on a 421 health check (`D-148`); Connect refused the form's own 0 cap and
hid why (`D-149`, `D-150`).

**The owner's decisions, 2026-09-25** — recorded in `DECISIONS.md` and
`OPEN_QUESTIONS.md`:
- Provider keys come only from the app. The environment-variable fallback is
  gone: it handed the owner's key to every workspace login (`D-151`, `DD-64`).
- Trust is the owner's to raise or lower, per provider and per model (`DD-65`).
- `Q-26` answered: stay on Render's free plan with a free hosted PostgreSQL
  (`DD-66`, `docs/architecture/HOSTED_STORAGE.md`, feature `F-06.03`, five
  phases). **Not built.** Until phase 1 (`S-06.03.02`) lands, everything on
  Render — keys included — is still wiped on every deploy.

**Built, DONE on 2026-09-28:** `S-06.02.31` (keys only from the app),
`S-06.02.32` (limit presets), `S-06.02.33` (trust per provider and model; also
`D-152`, `D-153`). Six fresh-context checks ran. The first found `D-154` to
`D-164`, two critical, in older code: a draft request or a profile could send
any server environment variable to any URL, and a client login could re-point
the owner's profile to receive the owner's key. The second found `D-165` to
`D-170`: the owner's fallback drafts used every workspace's profiles (high),
profile ownership was a label the request typed, lowering a provider
re-applied the full-data grant, and the call log was unscoped. Fixing those
found `D-171` — the full-data grant never sent more, older than this session —
and `D-172` to `D-175`. The third and fourth reviews (2026-09-26) found
nothing critical or high: `D-176` to `D-189`, four medium; the fourth
reviewer's look at its own findings' fixes found `D-190` to `D-193`, one of
them a regression in those fixes. The sixth check (2026-09-28) looked at those
fixes and found `D-194`, medium: the list and the click each worked out where a
waiting profile would go, so a workspace created in between could receive the
owner's key; and `D-195`, a screen-reader label that hid the destination. Both
fixed test-first; those two fixes were checked by tests and a real browser walk,
not by a seventh review. It also found `D-196`, older than this work — filed.
Re-reading the `D-194` fix before pushing found `D-197`: Enter in the key box,
or a browser that does not report the pressed button, took the first button —
the client workspace. Fixed test-first and walked in real Chromium.

**How profiles and trust work now — read before touching either:**
- A provider profile's owner is recorded by the server from the login — the
  install owner's is `local`, never a typed label. A draft uses only the
  caller's own profiles. Profiles saved before this wait for the owner to
  confirm them (`DD-68`, `POST /api/v1/provider-profiles/<id>/confirm`).
- The full-data grant reaches only a known model trusted at its provider's
  default tier or higher, and while it stands it decides what those models
  are sent; lowering the provider pauses it (`DD-67`). The owner's own level
  is never overwritten: Connect stores it cut only to the provider's standing
  trust. The per-model rule is `ProviderRegistry.resolve` (`grant_applied`);
  the screen's `sends`, `grant_state` and `grant_offer` are that function's
  answer per switched-on model (`describe`, `_grant_refusal` in
  `ai/workspace.py`). Change the rule in one place.
- Old profiles are settled in Settings, "Provider profiles to confirm":
  confirming takes the API key the profile holds — its label proves nothing.
  The list offers each one's destinations (`confirm_options`: the owner
  always, plus the client workspace its label names) and the pressed button
  sends one as `confirm_to`, by its own click; Enter confirms only a profile
  with one place to go. The server takes only an offered one, worked out
  again at the click (`DD-68`, `D-194`, `D-197`). A grant only ever lifts what
  is sent (`DD-67`).

**Found, not fixed:** `D-173` — Drafts reach a model only through provider
profiles, and no screen adds one since providers moved to Connectors. `Q-28`
asks which way drafts should go; `S-06.02.35` is filed for either answer.
`D-196` — a login made in workspace `local` acts as the install owner, and
nothing asks whether that was meant; `S-06.02.36`.

**Planned, not built:** `S-06.02.34` — show what is left per provider. Checked
on 2026-09-25: NVIDIA reports nothing; OpenRouter and DeepSeek do. A model
cannot know an account's balance; only a provider's API can say.

## 2026-09-24 — `S-06.02.24`: the command-line tools hold the restore lease

Building resumed at the owner's word, with the next READY item. Every
command-line tool that opens the workspace now holds the same shared lease as a
web request, for the whole command: `offsetx-outreach`, `-notebook`, `-evals`,
`-tools`, `-db` and `-artifacts`. During a backup or restore, or while an
interrupted restore awaits rollback, each refuses to start and says which. A
running one makes a restore answer 409, as a busy worker does. The helper is
`cli_workspace_lease` in `outreach/workspace_lock.py`.

Decisions made while building, with their reasons in the code:

- `offsetx-db` and `offsetx-artifacts` lock only when their target is inside
  the data directory. A Postgres check, or a run copied elsewhere, is nothing a
  restore swaps — and checking Postgres is what an operator does while a
  restore is stuck.
- Two refusal sentences, not the work order's one. A backup export takes the
  same exclusive lease, so "a restore is in progress" would have been wrong
  half the time.
- `data_paths.gmail_token_path` is now the one Gmail-token rule, and the web
  app reads it too, so the two cannot drift a third time.

Found while building, all fixed here: `offsetx-artifacts` writes into the
workspace (`D-139`); `.env.example` pinned the CRM and Gmail token outside the
data directory (`D-140`); the notebook read the AI context from the wrong
folder (`D-141`). Verified in a real run: six installed tools refused while a
separate process held the lease; a real HTTP restore answered 409 while a real
`offsetx-outreach import-contacts` held its lease, and succeeded after it ended.

The fresh-context review found one high defect this change widened: a tool
run as root left a lock file the app's user could not open, and every API
request answered 500 with health green (`D-142`). Fixed, with `D-143` to
`D-145`, each test-first. Open, and not claimed: `D-146` — a tool pointed at
the app's files from another folder, or with `OFFSETX_DATA_DIR` only in `.env`,
locks the wrong workspace; `S-06.02.28` owns it.

## 2026-09-23 — the handoff: the remaining work is written down, not built

The owner asked to stop building and to leave the rest as planned features, for
an implementer to build from. `BOARD.md` stays the one list: each item that
has a build plan carries a `work_order:` line pointing into `docs/work-orders/`.

New from this handoff: work orders for `S-06.02.24`, `S-06.02.25`,
`S-06.02.23`, `S-06.02.26`, `S-12.01.03`, `S-12.02.05`, `S-12.02.06` and the
close-out of `S-06.02.21`/`S-06.02.22`; the tenancy design for `S-06.01.06`
(`docs/architecture/CRM_TENANCY.md`); new stories `S-06.02.25` (`D-137`),
`S-06.02.26` and `S-06.02.27` (split from `S-06.02.23`); defects `D-137` and
`D-138`, both open with their stories. No code changed in this step.

## 2026-09-23 — the cold review of `develop`: ten defects, fixed

A reviewer in a fresh context read the consolidation's own code — the WP1
port, the campaign-selection port and the merge's `app.py` — and reproduced six
of its ten findings. Each is fixed with a test that failed first, and so is one
found while checking the fixes in a real browser:

| | Defect | Fix |
|---|---|---|
| critical | `D-124` any login could export the whole install (its admin token inside) or restore over it | owner-only: the token or the `local` login (DD-59) |
| high | `D-125` a workspace read another's product through drafts; any login ran the owner's content timer | a per-request caller marker; refused, not drafted blank (DD-60, DD-61); timer owner-only |
| high | `D-126` an external CRM database's WAL replayed over the other generation | sidecars move with the file, before it |
| high | `D-127` compose mounted the old data path; CLIs opened a second CRM | new mount; one path rule, `data_paths.py` (DD-63) |
| medium | `D-128` backups 500 on Python 3.10 | `wait_for`; the suite now runs on 3.10 |
| medium | `D-129` app would not start beside a busy worker; worker ran on a half-restored workspace | lock only with a journal, bounded wait; worker checks under its lease |
| medium | `D-130` a failed campaign list hid every screen, Settings included | only campaign screens wait |
| low | `D-131` the tool registry kept other threads' connections across a restore | tracks and closes all |
| low | `D-132` `api_token=`-style secrets passed the scanner | any `…token` name |
| low | `D-133` a long scheduled run held every request at 503 during a backup | timers stopped first, bounded; refuse, don't wait (DD-62) |
| low | `D-136` a failing campaign list always said "API access needed" | only a 401/403 says so; found in real Chromium |

Filed, not fixed: `D-134` (the CLIs write without the restore lease,
`S-06.02.24`) and `D-135` (CRM rows belong to no workspace — `Q-27`, the
owner's, with `S-06.01.06` waiting on it).

**What stays open.** `S-06.02.21` and `S-06.02.22` stay IN_REVIEW: their fixes
have tests but no second review, and the real-container and real-browser checks
ran before them — the browser walks were re-run on the fixed build (a created
campaign stays selected through Contacts and a reload; with the list failing,
Settings and its backup still show). `S-06.02.19` is BLOCKED on the branch
deletion. The image with
these fixes was built and run in real Docker: in the compose
layout a fresh `./local_data` became writable, kept a campaign across container
replacement, and refused a workspace login's backup and restore (403) while the
owner's export worked; the production acceptance (unprivileged user, kill and
recreate, restore, refusal on `/tmp`) passed again.

## 2026-09-23 — the branch consolidation: one working branch, `develop`

**What `develop` is.** Every piece of built work, on one branch. It started
from `feature/next-three-batch-4` (which contained `main`), merged the GTM
engine (E-12), the reports feature (`S-07.01.04`), the competitor research and
the frontend-audit record, and ported from `integration/main-consolidation` the
durable-state work (`S-06.02.21`), the campaign-selection fix (`S-06.02.22`) and
the owner's production contract. Every other branch was either already
inside it or built the same stories another way; each is to be kept as a tag.
`docs/BRANCHING.md` has the full record, the workflow and the renumbered IDs.

**What the consolidation found.** The newest line had never run its own
suite — CI could not start a runner (`D-75`), and nothing else ran it. On its
own it had 33 failing tests and 5 test files that could not load (`D-115`).
Root causes, all fixed with tests (`S-06.02.19`): every privacy route raised
NameError (`D-103`); the strict request schemas pre-empted the older endpoints'
readable errors and some requests the screens send (`D-107`); timers crashed
reading a login from a request they do not have (`D-109`); a bare `token=` in a
prompt passed the scanner (`D-110`); workspace-login installs could not start
(`D-111`); and several tests checked nothing (`D-104`, `D-105`, `D-108`). Its
restore lost data — a stale WAL replayed over the restored database, and the
backup named only four stores (`D-114`) — which the durable-state port replaced.
The Docker image could not build, on `main` too (`D-116`).

**Proven here, not assumed.**
- Full Python suite green, ruff gate clean, frontend tests and build green (the
  numbers are on the `Tests:` line at the top of this file).
- The real image, built and run in Docker with `OFFSETX_PRODUCTION=1` on a
  named volume, read-only root and no capabilities: kept a record and an asset
  through kill and recreate, restored a backup, stayed ready, and refused to
  start on `/tmp`.
- In real Chromium, the old code kept "First campaign" selected after
  "Second campaign" was created; `develop` keeps the new one through Contacts
  and a reload.

**Still open, on purpose.** The thirteen build-ahead stories stay IN_REVIEW —
the consolidation made them pass their tests, it did not review them.
`S-06.02.23` re-checks the other findings of the 7 September audit on
`develop`; two are known to be open (`D-121`, `D-122`). Both Render services
are free, so their data does not survive a restart (`Q-26`). CI still cannot
start a runner (`D-75`).

## 2026-09-23 — CHECK review of S-06.02.01, S-06.01.01 and S-06.01.04

The governing README was re-read first. Mode stayed CHECK, methodology Kanban,
role captain/architect. These stories were already IN_REVIEW, so this pass
audited production consumers and failure paths instead of creating new scope.

- **S-06.02.01 / D-79:** the scanner covered vendor-specific credential shapes
  but not generic assignments/field names such as `api_key=opaque-value` or
  `client_secret`. A bounded assignment rule plus the structural secret-field
  deny-list now block those values before provider instantiation.
- **S-06.01.01 / D-100:** `WorkspaceAISettingsStore` used per-instance thread
  locks around shared JSON/encrypted-key files. Concurrent processes could lose
  another workspace's update. Complete write windows now serialize through a
  standard-library SQLite write lock while the existing atomic replace remains.
- **S-06.01.01 / D-101:** the username regex double-escaped NUL/CR/LF and rejected
  normal characters such as r/n/x/0. The intended control-character regex and
  regressions are committed.
- **S-06.01.04:** cold review traced declaration → scheduler/event match →
  workspace lease → AgentRun → verified `notification` record → persistence.
  The two acceptance criteria remain enforced at production boundaries; no new
  code change was justified.

Work orders:
- `docs/work-orders/S-06.02.01-generic-secret-scan.md`
- `docs/work-orders/S-06.01.01-cross-process-settings.md`
- `docs/work-orders/S-06.01.01-username-validation.md`

The new workspace lock file contains no customer/settings/key data and requires
no migration. Rollback can remove the lock file while the application is
stopped; the existing JSON/encrypted-key formats are unchanged.

Executable proof is still unavailable because S-06.02.18 / D-75 prevents
GitHub-hosted jobs from reaching workflow step 1. None of these stories moves to
DONE without focused tests, full regression and the board verifier.

---

## 2026-09-23 — CHECK review of S-06.02.04, S-04.01.01 and S-02.02.02

The three requested stories were already code-complete and IN_REVIEW, so CHECK
mode audited acceptance criteria against production consumers rather than
restarting discovery.

- **S-06.02.04 / D-76:** a partial privacy retry cached old successful stores.
  Retry now re-inventories prior successes and re-deletes if matching subject
  data reappeared. The unchanged-success case still avoids a redundant delete.
- **S-04.01.01 / D-77:** the companion fixture used exact memory scope, but the
  real CRM store merges `global` into scoped searches. The shared store keeps
  that historical default for existing callers; companions explicitly use
  exact scope only. The regression now uses the real `OutreachStore`.
- **S-02.02.02 / D-78:** resume could recreate a deleted managed PLAN.md and
  lose owner edits. An empty private `.PLAN.managed` marker distinguishes a
  genuinely legacy run from managed state; managed plan loss now refuses.

Work orders:
- `docs/work-orders/S-06.02.04-retry-revalidation.md`
- `docs/work-orders/S-04.01.01-exact-memory-scope.md`
- `docs/work-orders/S-02.02.02-plan-loss.md`

Executable proof is still unavailable because S-06.02.18 / D-75 prevents GitHub
Actions from acquiring a runner. No story is promoted to DONE without focused
tests, full regression and the board verifier.

---

## 2026-09-22 — API, accessibility and local meeting batch

Three READY stories were implemented sequentially and moved to IN_REVIEW:

- `S-06.02.02`: one default-deny API middleware boundary plus a closed public
  bootstrap/signed-callback allowlist; route-enumerating auth tests and
  secret-safe request-validation errors cover the registered API surface.
- `S-06.02.05`: shared skip/focus/live-region/modal behaviour plus keyboard
  alternatives on custom interactions and recursive TSX accessibility
  contracts.
- `S-07.01.03`: browser-local microphone + shared system/tab audio mixing,
  MediaRecorder chunks, loopback-only capture mutations, one immutable
  transcription provider/model per meeting, transcript-only persistence,
  privacy deletion and encrypted backup/restore.

Batch review found D-65 through D-70. Meeting hardening fixed provider/model
redirection, privacy/backup registration and capture cleanup/recovery. API
hardening replaced 54 raw JSON request bodies with strict contracts. Accessibility
hardening fixed page-change focus and a hover-only tooltip. Close-out also found
and removed a duplicated S-06.02.02 board row before handoff.

Owner/manual verification is still required for the real local meeting capture
and keyboard/screen-reader pass. No story in this section is DONE.

---

## 2026-09-20 — second next-three implementation batch

Three additional READY stories were implemented sequentially and moved to
IN_REVIEW under DD-22:

- `S-03.02.05`: `browser/platforms.json` + validator now drive identity,
  domain policy and default budgets from one declaration. Reddit demonstrates
  data-only onboarding. No browser verb or executable plugin surface was added.
- `S-02.02.02`: `agent/plan.py` gives each trace run exactly one PLAN.md,
  read fresh before every broker decision. Owner edits affect the next call;
  the exact consumed plan version is captured in that decision's trace artefact.
- `S-04.01.01`: `agent/companions.py` persists profiles as rows inside the
  existing ToolRegistry SQLite DB. Runtime uses only the companion's exact
  approved-memory scope and enabled granted tools; tool execution enforces the
  grant again. Authenticated CRUD/context/memory endpoints are wired.

Integration review found D-59 through D-64. The important corrections were:
replace process-local JSON companion storage with transactional SQLite; register
companion profile text with privacy deletion; and close/reconstruct tool and
companion stores around backup restore.

Remote Actions close-out evidence: run 971 (`35470919395`) on HEAD `dbe9d7fd2` created one `quality` job, failed in ~2 seconds with `steps: []`, `runner_id: 0` and no runner name. No repository command executed, so this is infrastructure evidence, not a failing product test.

Verification remains deferred by owner instruction. Focused commands are
recorded in DEMO.md and TRACEABILITY.md; do not promote these stories to DONE
without executing them, full regression and the board verifier.

---

## 2026-09-20 — next three implementations complete, verification deferred

The owner explicitly authorised build-ahead (DD-22): implementation may
continue across code-complete IN_REVIEW dependencies, but no downstream story
may be called DONE ahead of its evidence/dependency chain.

The requested batch is implemented and all three stories are IN_REVIEW:

- **S-05.01.02 — extraction packs.** Validated repository-controlled JSON
  declares domain, record selector and bounded text/attribute fields. It reuses
  Scrapling and the existing URL/robots/SSRF path; no executable plugin or AI
  extractor was introduced. Generic JSON-LD remains the fallback.
  CHECK-mode cold review on 2026-09-23 found D-72: malformed CSS selectors
  previously loaded successfully and could fail only during page parsing. The
  registry now validates selectors with Scrapling itself before installation,
  and pack selectors cannot supply text/attribute pseudo-elements.
- **S-05.01.03 — competitor teardown.** Normalized public structural/performance
  facts map deterministically to an existing video recipe. Copied media/caption/
  transcript fields are rejected. Projects use our own material and enter the
  existing human review queue.
  CHECK-mode cold review on 2026-09-23 found D-73: NaN/Infinity could pass the
  non-negative numeric validator and later crash tick conversion or contaminate
  performance evidence. All numeric facts now reject non-finite values before
  recipe selection or arithmetic.
  The same review found D-74: a removed/renamed declared recipe escaped as
  `UnknownRecipe` and would become an API 500. Recipe resolution now fails as a
  controlled `CompetitorTeardownError`, preserving the catalogue reason.
- **S-06.02.04 — subject access/deletion.** Authenticated, workspace-bound access
  and confirmed deletion use one eight-adapter inventory covering CRM/research/
  delivery data, recall, AI context/egress, tagged artifacts, CSV queues/exports,
  crawler state and trace runs. Partial failures stay partial and retry safely;
  CRM identity rows delete last.

Review found and fixed D-53 through D-58 before owner testing. Focused tests are
in `tests/test_extraction_packs.py`, `tests/test_competitor_teardown.py` and
`tests/test_privacy.py`.

Do not promote these stories from IN_REVIEW until the dedicated verification
pass runs the DEMO.md commands, the full regression and
`uv run python scripts/verify_board.py`.


---

---

## 0. Session setup

`.claude/hooks/session-start.sh` runs on every session. It prints the repository
name, branch, HEAD and commit count **first**, then installs Python and frontend
dependencies so tests and linters work immediately.

The identity banner exists because of a real incident: a session started against
the empty sibling repo `email_agent`, found no commits, and reported "your repo
is empty" instead of noticing it was in the wrong place. A repo that announces
itself makes that failure impossible rather than unlikely. `AGENTS.md` carries
the same warning for the same reason.

---

## 1. What this module is

An AI layer inside off_CRM that runs outreach cheaply across many providers,
where the owner's mailbox, CRM database and context layers are **structurally**
unable to reach any provider.

The governing rule: **models never pull, off_CRM pushes.** A model that can
*ask* for data has access. A model that can only *receive* a constructed payload
does not.

---

## 2. Architecture as built

```
offsetx_apollo_builder/ai/          ← self-contained, extractable (§4M)
├── tiers.py      trust tiers, data classes, policy levels, the rules between them
├── registry.py   reads config/providers.yaml; resolves provider + owner override
├── payload.py    builds outbound payloads from an ALLOWLIST, starting empty
├── scanner.py    pre-flight scan; a hit BLOCKS and raises, never redacts
├── quota.py      local RPM/RPD/spend accounting, file-backed
├── broker.py     THE single egress gate — the only code that calls a provider
├── modes.py      run modes: simple, verified, compare, orchestrated
├── verify.py     write -> check -> repair -> review
├── sandbox.py    container isolation for AI-written code (§4J)
├── abstraction.py widens the *shape* of a request: bands, stages, margins
├── bandit.py     Thompson allocation between approved template variants
├── cache.py      exact + lexical near-match response cache, keyed on the payload
├── tools.py      the registry of owner-pinned tools that may run in it
└── tool_cli.py   `offsetx-tools` — register, inspect, run
├── discovery.py  asks a provider what models its key reaches
├── log.py        egress log; own table, exact payload, SQLite or Postgres
├── workspace.py  per-workspace settings + Fernet-encrypted provider keys
├── errors.py     structured refusals the API turns into readable answers
└── failures.py   what kind of failure this was, and what to do about it

config/providers.yaml               ← the registry. Adding a provider is a
                                       config edit, never a code change (§4E)

offsetx_apollo_builder/distribution/ ← the content distribution runner
├── platforms.py  what each platform permits, and what off_CRM refuses
├── youtube.py    Data API v3 read client; the only transport in the package
├── trends.py     competitor watch list + what is actually rising
├── topics.py     what several channels are covering at once
├── pipeline.py   trend -> brief -> swipe -> caption -> draft post
├── publishers.py the adapter interface + the local outbox
├── store.py      accounts, posts, goals, engagement snapshots
└── engine.py     plan -> approve -> schedule -> publish -> measure

offsetx_apollo_builder/imagery/     ← the image campaign runner
├── gates.py      deterministic quality gates; header parsing, no image library
├── store.py      briefs, candidate assets, generator scores
└── engine.py     generate -> gate -> review queue -> swipe -> score

offsetx_apollo_builder/video/       ← the timeline editor (CapCut's shape)
├── timeline.py   the document, its invariants, and the frame resolver
├── edits.py      every edit as a pure function; a default-deny registry
├── gates.py      MP4 + WebM + WAV header parsing; gates on the exported file
├── presets.py    transitions, animations, text styles and speed curves, as data
├── recipes.py    whole-video shapes: beats, shares, which preset each beat uses
├── assembly.py   material + recipe -> a finished project, and the edit-diff
├── director.py   a topic -> a shape and the words; the model's reply, checked
├── mixdown.py    the audio mix as a gain-envelope plan the browser executes
├── captions.py   transcript -> readable cues -> text clips, deterministic
├── store.py      projects, version history (undo), media, transcripts, renders
└── engine.py     create -> edit -> undo -> caption -> render -> gate

frontend/src/video/                 ← the half that needs a GPU and a codec
├── resolve.ts    the frame resolver again, pinned to Python by one fixture
├── mixdown.ts    the gain-envelope planner again, pinned by the same fixture
├── audio.ts      OfflineAudioContext mix -> Opus chunks for the muxer
├── demux/        MP4 and WebM read for their frames, by hand
├── footage.ts    a decoder, a cursor and a frame cache, per video clip
├── render.ts     paints one resolved frame; the preview and export share it
├── webm.ts       the muxer; the only thing that writes the finished file
└── export.ts     load -> mix -> paint -> encode -> mux -> upload

offsetx_apollo_builder/             ← deliberately OUTSIDE ai/
├── intake.py     two-mode campaign intake; a contact list never meets a model
├── campaigns.py  the registry of campaign kinds; email is one of them
├── notebook.py   research-notebook export; the destination is a trust tier
├── notebook_cli.py  `offsetx-notebook` — targets, plan, export
├── codegraph.py  Graphify wrapper; keeps the semantic path switched off
├── codegraph_cli.py `offsetx-codegraph` — policy, build, status, verify
├── db/           backend seam: SQLite or Postgres behind one interface
└── db_cli.py     `offsetx-db` — check the backend, copy the egress log
```

The module depends on the CRM only through `outreach/models.py` (dataclasses)
and `outreach/providers.py` (HTTP adapters). Lifting it into its own repo means
taking those two seams with it.

### The call path

```
caller → EgressRequest (task_type, data_class, person, template…)
       → broker.plan()      1. tier filter   ← runs FIRST, cost cannot override
                            2. quota filter
                            3. same-tier-only chain
       → build_payload()    4. construct from empty, per resolved policy
       → scan_payload()     5. block + raise on any hit
       → provider.generate  6. call
       → log.record()       7. record provider, tier, exact payload, timestamp
```

### Trust tiers (owner's ordering, 2026-07-25)

| Tier | Who | Policy ceiling | May receive |
|---|---|---|---|
| A | Europe, self-hosted | full | public, person, campaign, CRM internal |
| B | USA, Canada, allied | standard | public, person, campaign |
| C | China, and anything demoted for weak data terms | pseudonymous | public, person's public profile **as tokens** |
| D | Routers/aggregators, anything unlisted | strict | nothing |

Tier is derived from **two axes** — jurisdiction *and* retention terms. Passing
one is not enough. Google's free tier sits at C despite being US-based, because
its terms allow training on submitted content.

### Data policies (least → most)

| Policy | Sends |
|---|---|
| `strict` | Category and question structure. Nobody identifiable. |
| `pseudonymous` | Job title, category and the public hook, with the person and company as `PERSON_1` / `COMPANY_1`. Free text is scrubbed of the name too. Nobody identifiable. **Tier C ceiling.** |
| `minimal` | The person's public name, company, title, hook + your positioning line. Addresses tokenised. |
| `standard` | Above + your template text and campaign notes. Addresses tokenised. |
| `full` | No field restrictions. Real addresses can leave. Explicit opt-in. |

**Note on `minimal`:** it deliberately permits the person's public name so
enrichment can personalise — the owner's instruction. It is now reachable only
by tiers A and B: tier C's ceiling was lowered to `pseudonymous` (owner's
decision 2026-07-31, reversing §5.2 below). The older `outreach/providers.py`
path keeps its own stricter meaning for `minimal`; the two are documented
separately so existing profiles never silently widen.

`full` stays available on any tier via a recorded override with a mandatory
reason. Credentials, mailbox headers and internal field names are blocked at
**every** policy level including `full`.

---

## 3. Done

### The GTM engine — Phase 1 and 2 (E-12, 2026-09-22)

The owner's end goal is an autonomous GTM engineer. Phase 1 gives the system one
source of truth about the product; Phase 2 is the brain that plans, applies,
reviews and revises. Design, data model, API and work orders:
`docs/architecture/GTM_ENGINE.md`. Decisions `DD-40`–`DD-54`; defects
`D-80`–`D-84`; open questions `Q-20`–`Q-24`.

- [x] **`offsetx_apollo_builder/gtm/`** — `products.py` (validation, forbidden
      claims), `store.py` (the only code touching `gtm_*` tables),
      `strategy.py` (plan request, envelope, parse, rules plan, feasibility),
      `review.py` (diagnosis, remedies, revision) and `service.py` (the one
      stateful orchestrator). **It imports nothing from `ai/` and no transport**;
      `tests/test_gtm_products.py` walks the package's AST to hold that.
- [x] **The model never builds structure.** It chooses from declared lists and
      writes short sentences; code decides volume from what is connected and
      always sends on `targeted_outreach`. Its reply is untrusted input, checked
      field by field (`DD-40`).
- [x] **The owner's words travel only in classified fields** — the one-liner as
      the positioning line, the rest as campaign notes — never in the system
      prompt or `instructions`, which the data policy does not govern (`DD-41`,
      `D-81`). Requests are `DataClass.CAMPAIGN`, so tiers C and D never see them.
- [x] **Apply creates paused campaigns**, imports nobody, spends nothing and
      sends nothing (`DD-42`); it is idempotent per channel (`DD-49`).
- [x] **Review in a fixed order** — delivery, running, contacts, approvals,
      volume, and only then the copy, by a 90% Wilson interval after 20 sends
      (`DD-45`, `DD-47`, `DD-50`). Every review is stored with exactly what it
      measured: the first labelled data this product owns, and what a fine-tune
      would train on when the owner builds it last.
- [x] **Revise** carries the measured rate forward, keeps the deadline, and
      judges each version on its own sends (`DD-53`, `DD-54`).
- [x] Screens: **Product** and **Go-to-market plan** (plan, apply, review,
      revise). No button leads nowhere: a step no screen can do yet is shown
      without a link and says so.
- [x] 184 GTM tests across six files, plus 4 UI tests; all six stories `DONE`
      after a cold review by a reviewer that never saw the code being written.
      It found 13 problems (`D-87`–`D-99`); 12 are fixed, each behind a test that
      failed first, and one is filed (`D-97` → `S-12.02.06`). The worst:
      pausing a posting campaign did not stop posting (`D-87`), and a revised
      angle reached nothing that is sent (`D-89`).
- [x] Walked in a real browser (headless Chromium against the running app):
      product → plan → apply → review → revise, and the Product screen's link
      checklist. The migration's rollback was executed once (`GTM_ENGINE.md` §4).

**Not built here, on purpose:** the video director reading the product
(`S-12.01.03`, blocked on `D-81`); drafting against the expert corpus
(`S-12.02.05`); running a plan's posting channel from the screens (`S-12.02.06`,
`D-82`); video in the email (`F-12.03`, Google Drive for now — `Q-20`); driving
Apollo, Hunter, Clay and Mailchimp as tools (`F-12.04`); compiling an audience
into an Apollo search (`F-12.05`); creating social accounts in bulk (`Q-21`,
open — it conflicts with the sock-puppet row and the FTC rule on fake
influence).

### Protected bulk email delivery (beta, F-08.01, 2026-08-24)
- [x] Added deterministic permission, relationship, global-suppression,
      frequency, send-window and unsubscribe preflight. AI is not part of any
      send-policy decision.
- [x] Added stream- and domain-isolated sending identities with SES verification,
      seven-day SPF/DKIM/DMARC/alignment freshness, configuration-set and signed
      SNS-topic requirements. AWS credentials stay in the normal SDK chain.
- [x] Added schema v9 durable jobs with immutable message snapshots, atomic
      SQLite claims, cross-path daily caps, per-lane rate/backoff state, bounded
      retries and `delivery_unknown` quarantine after ambiguous provider state.
- [x] Added public HMAC one-click unsubscribe, RFC 8058 headers for permission
      marketing, hard-bounce/complaint suppression, idempotent feedback,
      campaign health thresholds, auto-pause and explicit resume.
- [x] Reply sync now cancels already queued jobs. Temporary pauses and closed
      send windows defer without consuming a provider attempt; cancellations
      are conditional and cannot race a claimed job into an operator cancel.
- [x] Added SES v2 raw-MIME transport, a separate `offsetx-email-worker`, API
      surface, exact `QUEUE LIVE EMAILS` confirmation and a Deliverability UI
      with loading/error/empty states, identity checks, permission evidence,
      suppression, job cancellation and health resume.
- [x] Core evidence re-certified under S-08.01.01–04 on 2026-08-27: 16 focused
      delivery tests and the complete 1,461-test Python suite pass. The latest
      known frontend evidence remains 116 tests and a production build from the
      implementation session; S-08.01.05 stays in review until its dashboard
      test is re-run. Live AWS/domain/mailbox-cohort validation is still
      explicitly required; see `docs/architecture/EMAIL_DELIVERY.md`.

### Open-source release hardening (2026-08-20)
- [x] Replaced the stale public README with the current product boundary: CRM,
      public-page lead discovery, AI routing, image campaigns, video editing,
      content distribution and the Stage-1 browser agent, with stable/beta/alpha
      status and external-provider costs stated plainly.
- [x] Removed real professional contact details from the public sample exclusion
      CSV and from the unit-test fixture that repeated one of those identities.
- [x] Repaired the locked install. `websockets` is now represented as a direct
      dependency in `uv.lock`, and the exact CI command `uv sync --extra dev
      --locked` succeeds on a clean environment.
- [x] Fixed `POST /api/v1/ai/run` in verified mode: a non-empty `checks_suite`
      called an undefined `_evals_path()` and returned 500. Eval config now has
      one shared resolver, an environment override, a packaged fallback and a
      drift test, so both source checkouts and installed wheels load the same
      rules.
- [x] Raised `cryptography` to 50.0.0 and `pypdf` to 6.16.1, clearing the known
      Python dependency advisories found in the release audit.
- [x] Added a focused Ruff CI gate for syntax and undefined names plus smoke
      tests for every installed CLI entry point. The gate would have caught the
      verified-mode failure before release.
- [x] Verified the full result: 1,416 Python tests, 115 frontend tests, frontend
      production build, CLI smoke tests, lock check, package compatibility and
      dependency audit all clean.

### Security core (§5)
- [x] Single egress gate. `create_provider` is reachable only from `ai/broker.py`,
      `outreach/providers.py` and `outreach/provider_profiles.py`; enforced by
      an AST test that walks every module.
- [x] Two former bypasses fixed: `api/app.py` (request-supplied provider) and
      `outreach_cli.py` now go through `create_guarded_provider`, which cannot
      return an unwrapped provider.
- [x] Payload **construction** replaces filtering. `PersonPublic` has no email
      field, so an address cannot arrive through the person path at all.
- [x] Pre-flight scanner blocks and raises. Catches addresses, owner domains,
      credentials (12 shapes), mail headers, internal field names, env vars,
      local paths.
- [x] Trust tiers on both axes, with per-model provenance caps (a US host
      serving a Chinese-origin model is capped at C).
- [x] Default-deny: an unlisted provider raises rather than being assumed safe.
- [x] Fail-closed: unknown tier, empty candidate set and exhausted quota all
      stop the call.
- [x] Failover never crosses a tier boundary.
- [x] Mailbox is unreachable by default for every provider; unlock needs the
      exact phrase `ALLOW MAILBOX CONTENT TO LEAVE`, and even then tier C is
      still refused.
- [x] Egress log with the exact payload + inspector UI (`#egress`).
- [x] Credential isolation: Fernet, `0600`, per workspace, env fallback.
- [x] §5.12 acceptance tests — 30 cases in `tests/test_ai_egress_wall.py`.

### Run modes (owner's design, 2026-07-25)
- [x] **Simple** — one model, cheapest permitted. The everyday path.
- [x] **Compare** — every permitted model answers at once, side by side. Each
      runs under *its own* policy, so a tier C model can contribute without
      seeing more than it should. Capped at 8 branches so one question cannot
      burn every quota.
- [x] **Orchestrated** — a head model writes a plan, each step routes normally.
      **The head model must be tier A or B.** Planning means seeing the whole
      job, so restricted models get steps to do, never the job to split.
      A plan cannot widen its own reach: a step asking for `mailbox` or
      `internal` is clamped to what the caller already offered.
- [x] Model strip in the AI screen: every connected AI, its trust badge, and a
      meter showing how close it is to its daily limit.

### Per-model connectors (2026-07-26)
- [x] A connector is a **key**, and a key reaches many models. One NVIDIA key
      offers Llama, DeepSeek, Qwen, Phi, Gemma, Granite, Mistral, Nemotron.
- [x] **Tier belongs to the model, not the key.** NVIDIA+Llama is B,
      NVIDIA+DeepSeek is C — in the same run, on the same key.
- [x] `model_origin_rules` in config classify a model by name prefix. The
      provider supplies names; config decides trust. Unmatched name -> tier D.
- [x] "Find models" calls the provider's `/models` endpoint. Sends no owner
      data; still written to the egress log so the record stays complete.
      Degrades to the config list on any failure, with the reason shown.
- [x] Connecting a model off_CRM cannot place is refused with the fix in the
      message, rather than failing later at call time.
- [x] **Per-model `request_options` in config** — `max_tokens`, `temperature`,
      and provider-specific keys such as NVIDIA's `reasoning_budget`. A large
      reasoning model with no `max_tokens` gets truncated by the provider's
      own default, so this is correctness, not tuning. Options are opt-in per
      model; models that declare none send a plain payload.
- [x] Reasoning models handled: `reasoning_content` is returned when
      `content` is empty, and `finish_reason: length` produces an error that
      names `max_tokens` as the fix instead of "no message content".
- [x] Nemotron Ultra 550B and DeepSeek R1 seeded with working options.
- [x] **Image generation.** Models carry `kind: chat | image`; image models
      go to `/images/generations` and return pictures. Same key, same tier
      rules, same scanner, same log — a prompt is text, so a prompt naming a
      real person is still person data. FLUX (German) and Stable Diffusion
      (British) seeded on the NVIDIA key with origin rules for their makers.
      Pictures come back as base64 so they never sit behind a provider URL;
      the image itself is not written to the egress log, only the prompt and
      a count, since the log exists to show what *left*.

### Fixed in this round
- [x] **The chosen model was ignored.** `candidates_for` resolved each provider
      with no model id, so every call fell back to `default_model` — and the
      provenance cap was therefore unreachable from the UI: picking a Chinese
      model on NVIDIA was treated as tier B. Three call sites had the same gap
      (broker, compare, orchestrated planner); all now route per model, each
      with a regression test.

### Features
- [x] §4B Connectors: own screen; Gmail moved out of Settings; every provider
      card shows **country, trust tier, retention terms**, usage and cost.
- [x] §4C AI chat: model selector, task mode, Markdown/HTML export, dictation
      where the browser supports it (degrades silently where it does not).
- [x] §4E config-driven registry: 17 providers in YAML with jurisdiction,
      retention, RPM/RPD, context window, cost, `verified_on` date.
- [x] §4E local quota counting + usage display + same-tier failover.
- [x] §4L: structured refusals surface as readable sentences with a next step,
      never a raw status code. Every empty state has an action.

### Context layer (§4F/§4H) — built

- [x] `ai/context.py` — job state (steps, decisions, facts) plus a **rolling
      summary assembled by Python**, not written by a model. Same inputs, same
      summary; no per-update AI cost and no drift.
- [x] Decisions survive a model swap mid-job, which is the point of the layer:
      the head model can change without the choices being quietly undone.
- [x] Reply-rate counting per template and variant. A template is not judged
      until 20 sends, so one lucky reply out of two is never a "50% success".
- [x] Weak templates (judged, at or under 5%) can be rewritten. The request that
      leaves carries **the template wording and two numbers** — no recipient, no
      name, no address — so it runs as public work under any permitted model.
- [x] Nothing goes live automatically. A rewrite is shown for approval and saved
      as a new variant to run against the old one.
- [x] The winning template is offered to other models as a reference to follow
      or beat (owner's request).
- [x] **Wired into the real send path.** `OutreachEngine` counts a send when the
      message actually leaves and a reply against the template that was sent —
      not the contact's current stage, which has usually moved on. The unattended
      automation sender counts too. A counter failure can never lose a send.
- [x] Two safety rules with their own tests: **no model can query this store**
      (no tool, no function, no retrieval interface, no provider import), and
      **only code writes to it** — so the numbers stay facts.
- [x] `record_reply` takes no reply text. Detecting that a reply arrived is a
      fact; reading what it says would be mailbox content leaving. There is
      nowhere to put it.
- [x] Memory screen in the UI: reply rates, weak flags, the rewrite awaiting
      approval, and jobs in progress.
- [x] This is **not fine-tuning**. No data is shipped away to retrain anything.

### Eval harness — built (2026-07-31)

Answers what the run modes could not: does orchestration beat one good model?

- [x] `ai/evals.py` — twelve **deterministic** check kinds, pure functions of the
      output text. No model judges anything, for the same reason no model
      enforces policy: a grader that varies is not a measurement.
- [x] An unknown check kind **fails** rather than passing, so a typo in a check
      name cannot silently inflate every score that uses it.
- [x] `config/evals.yaml` — suites are config, like `providers.yaml`. Adding a
      case is a data edit.
- [x] `ai/scoreboard.py` — run history, leaderboard, and the champion per suite.
- [x] **Champion/challenger gate.** A mode is promoted only if it beats the best
      single model on the mean, **and** wins case-by-case beyond chance, **and**
      stays inside a cost ceiling. Every other path keeps the champion.
- [x] Significance by **exact binomial sign test**, not `>`. Both subjects run
      the same cases, so the comparison is paired. Comparing raw means on a
      thirty-case suite flips the winner on noise about half the time when the
      two are actually equal, and every flip costs money because the challenger
      runs several models per task.
- [x] `route_for()` returns `simple` when nothing has been measured. An
      unmeasured system routes to one model, never to an unchecked ensemble.
- [x] `offsetx-evals` CLI: `list`, `run --modes`, `champion`, plus `--dry-run`
      that prints the call count without spending tokens.
- [x] Same rules as the rest of the module: evals go through the broker with
      ordinary tier rules (verified against a tier D aggregator), and **no model
      can read or write the scoreboard** — asserted by an AST walk.

**First result, and the reason this was worth building.** On the shipped suite,
compare mode scored *identically* to the champion — not close, equal — because
`first_permitted_text` returns the highest-tier branch, which is the champion's
own answer. Compare mode paid for two calls and returned what one model would
have said alone. That is fine for its designed use (the owner reads every branch
and picks) but means calling it programmatically buys nothing. Nobody could have
known without measuring.

**Honest limitation:** seven cases ship. That is a skeleton, not a suite. Thirty
or more is the floor for trusting a close verdict, and the CLI warns on every
`list`. The cases worth adding are ones from real work that disappointed you.

### Two-mode intake — built (2026-07-31)

Two ways a campaign gets its people, kept apart because conflating them is how
mistakes happen. **Generate**: describe who you want, discovery finds them.
**Parse**: you already have the list — CSV, spreadsheet or PDF.

**Deliberately outside the `ai/` package.** A contact list is the densest
concentration of exactly what the system protects — real names, addresses,
companies. If a model parsed it, that one feature would leak more than every
other path combined. Parsing is deterministic and local; a test walks the module
and fails the build if it ever gains a route to a provider or an import from
`ai/`. Same rule as the campaign runner: the parts touching real contacts have
no AI, the parts with AI have no real contacts.

- [x] CSV and XLSX through the existing loader. A column is a column, so nothing
      is flagged and the result is immediately usable.
- [x] **PDF reading via `pypdf`, locally.** Addresses are found exactly — an
      email has a shape a pattern matches. Names are inferred from layout: the
      same line first, then the line above, which are the two arrangements a
      printed table actually uses.
- [x] **Every PDF row is flagged `needs_review` and can never be sent
      unreviewed.** Not a placeholder for better parsing later — guessing which
      name belongs to which address and being wrong means emailing a real person
      by the wrong name. `ready_to_send` is False whenever anything is flagged.
- [x] When no name is convincing, the row says "no name found near this address"
      rather than guessing. A wrong name is worse than a missing one.
- [x] Column headers are not mistaken for people; duplicate addresses read once;
      page numbers recorded so a row can be found again.
- [x] **No OCR.** A scan has no text layer, and pretending otherwise produces
      confident nonsense — the warning says to export the original as CSV.
- [x] Refusals are readable: missing file, unsupported type, a file that is not
      really a PDF.
- [x] Generate mode is a validated brief. No contact in a generated list is
      invented by a model; the data source produces them.

**Defect found while building.** The row builder read `full_name` and `company`,
but `normalize_input_rows` emits the CRM's own field names, `name` and
`organization_name`. Every parsed row came back with no name — which looked like
a parsing failure and was really a mapping one. Caught by exercising it against
a real CSV rather than trusting the field names. Regression-tested.

**Not built:** no UI screen, and wiring generate mode to discovery is separate
work. Tests build a real PDF by hand rather than mocking extraction, so the
genuine `pypdf` path is exercised without adding a test dependency.

### Response cache — built (2026-07-31)

**Named honestly.** The literature's "semantic cache" and its 60-90% hit rates
come from chat systems where users repeat questions. Personalised outreach gives
every payload a different token and hook, so those numbers do not transfer. It is
also not embedding-based — that would mean a network call from a module whose
point is avoiding calls, or a heavy dependency. It does exact match plus lexical
near-match, which fully covers where caching actually pays here: re-running eval
suites, retries, verify-loop repair rounds, and repeated public or code work.
The cache reports its own hit rate, because whether it earns its place is a
question for the owner's numbers rather than a published average.

- [x] **Keyed on the constructed payload**, not the question. Payloads are built
      per policy — verified, not assumed — so a response produced from a richer
      payload can never be served for a thinner one. That matters beyond the
      obvious: a response can travel back out as `prior_drafts`, so a cache that
      blurred policy boundaries would be a slow path for tier A material to
      reach a tier C provider.
- [x] Partitioned by workspace, data class, policy, task type and provider.
      Near-matching is confined to one partition, so fuzzy comparison cannot
      cross a boundary however similar two texts look.
- [x] **Consulted after construction and scanning, never before.** A lookup must
      not become a way around the checks that precede it — if the scanner
      blocks, nothing is served and nothing is stored.
- [x] **A hit is logged as `cache_exact`/`cache_near`, not `succeeded`.** Nothing
      left the machine, and the egress log is the one thing that must never lie.
- [x] Near match at 0.92 Jaccard over **word triples**. Single-word overlap would
      call two different questions similar; triples require the phrasing to line
      up. The threshold errs towards missing, because serving a stale answer to
      a different request is worse than missing a hit. Switchable off.
- [x] Never stores empty responses or failed calls — that would turn one
      transient outage into a week of them — and never stores `MAILBOX`.
- [x] 7-day TTL, 5,000-row cap with oldest-first eviction, manual purge and
      clear. A cache, not an archive; the egress log holds the record.
- [x] Exact and near hits counted separately, since they carry different risk.

### Traffic shifting — built (2026-07-31)

`context.py` counts sends and replies; this decides the split. Thompson sampling
over Beta posteriors, in `ai/bandit.py`, reached through
`context.traffic_split()`.

**Why not a threshold.** The arithmetic of low reply rates rules it out:
separating 2% from 4% needs ~1,140 sends per variant, 2% from 3% needs ~3,800,
and twenty sends with no replies has a 54% chance of occurring even at a healthy
3% true rate. A threshold rule fed that data does not become cautious — it
becomes confidently wrong.

- [x] Thompson allocation: the share a variant wins **is** its probability of
      being best. Near-even when posteriors overlap, shifting as they separate —
      correct at both ends with no cut-off to choose. That graceful degradation
      is the whole reason for the choice: a threshold has to be right, this does
      not.
- [x] `sends_needed()` tells the owner how far off an answer is. On two nearly
      identical rates it reports tens of thousands of sends, which is the useful
      answer: stop trying.
- [x] 5% floor per active variant. Without a holdout a winner that later
      degrades looks fine forever, and a variant unlucky in its first twenty
      sends could never recover.
- [x] Rates reported as posterior means, not raw fractions — one reply from two
      sends is not a 50% reply rate.
- [x] Seeded runs are reproducible, so a split can be re-derived later.
- [x] Retired variants excluded entirely. Structural test: `bandit.py` imports
      no database and no provider, so the maths can be tested exactly.
- [x] **Decides how much, never whether.** It allocates only between variants
      the owner already approved; an unapproved rewrite is not an active row for
      it to see, so it cannot promote one. §3 is unchanged.

**Defect caught while building.** The verdict read "traffic stays near even"
while allocating 80/20 — the sentence contradicted the numbers. Thompson does
shift below the confidence bar; the text was simply false. It now describes the
real split, with a parametrised regression test asserting the even-split wording
only appears when the leader is under 65%.

### Abstraction layer — built (2026-07-31)

Tokenisation hides *who*. This hides *how the business works*, which no PII rule
touches. Verified against the real builder first: a tier B provider was
receiving company size, funding stage, the stated ICP band, the **gross margin**,
the **close rate**, the sequence length and engagement counts — verbatim, with
every identifier already removed.

- [x] `ai/abstraction.py` + `config/abstraction.yaml` — 14 deterministic rules,
      three kinds (`bucket_number`, `replace_pattern`, `replace_terms`). Rules,
      not a model: a protection that varies is not a protection.
- [x] **Every rule only ever widens.** None can make text more revealing, which
      is why applying it twice is safe — asserted by an idempotence test.
- [x] Applied below `full` only; at `full` the owner has explicitly trusted one
      provider with everything. Off per workspace via `abstract_business_shape`,
      defaulting **on**, so a caller that forgets gets protection not a leak.
- [x] Loud config validation: unknown kind, missing `(?P<value>)` group, absent
      open-ended bucket and malformed pattern all raise at load. A rule that
      silently does nothing is worse than no rule, because it looks like
      protection.
- [x] A broken rules file does not stop a send — failing to widen must not
      become failing to send.

**Three defects found and fixed, each with a regression test.**

1. **The margin was leaking.** The percentage rule ended in `\b`, and `%` is not
   a word character, so that boundary can never match. The single most
   commercially sensitive number in a payload passed straight through the rule
   written to catch it.
2. **A rule was lying.** The sequence-position rule turned "a warm *first*
   email" into "a warm *a later message in the sequence*", inverting the
   meaning. Caught by an existing test failing. `first` is now left alone
   entirely: every sequence has a first message, so the word leaks nothing —
   it is the high ordinals that disclose how many steps exist.
3. **Rule order was wrong.** `headcount` preceded `headcount_ranges` and
   consumed the right-hand number of "100-250 staff", so the range rule never
   fired. The more specific pattern must run first.

Cost to quality is near zero: ordinary copy instructions pass through untouched,
and where the rules do fire they leave the useful signal intact.

### Tool registry — built (2026-07-31)

The list of who may enter the locked room. One sentence carries the design:
**a model names a tool that already exists; it cannot describe a new one.**

- [x] `ai/tools.py` — register, list, enable/disable, remove, run, run history.
- [x] **`run()` takes a `tool_id`, never an image or a command.** A test asserts
      this at the *signature* level: if the parameter list ever grows `image=`
      or `command=`, the build fails, because the registry would have stopped
      being a registry.
- [x] Three mandatory pins, none defaultable: a `github.com/owner/repo` URL, a
      **full 40-character commit SHA** (branches and tags refused — they move),
      and a version-pinned image (`:latest` refused).
- [x] **The catalogue withholds the recipe.** A model sees id, name, description
      and whether arguments are accepted. No image, no command, no repository —
      so a leaked catalogue is not a leaked attack surface. A disabled tool is
      *absent* rather than marked, so a model cannot tell it exists.
- [x] Extra arguments are **opt-in per tool**, capped at 8, values only —
      anything starting with `-` is refused so a caller cannot change how the
      tool behaves.
- [x] **Source is fetched on the host, not in the container.** The container has
      no network, so it cannot clone; off_CRM materialises the pinned commit
      first and then proves `rev-parse HEAD` equals what was registered. That
      puts the integrity check somewhere a compromised tool cannot reach. Source
      lands in `inbox/`, which mounts read-only, so a tool cannot rewrite its own
      source mid-run.
- [x] Every run is logged with **the commit and image it actually used**, not
      just the tool name. A timeout is recorded as a run, not raised away.
- [x] `offsetx-tools` CLI: `register`, `list`, `show`, `catalogue` (prints
      exactly what a model would see), `run`, `enable`/`disable`, `remove`,
      `runs`.

**Defect found and fixed while building this.** `sandbox_available()` checked
for the docker *binary* with `shutil.which`, which is not the same as a running
*daemon* — the dev machine has the binary and no engine, and the first CLI run
sailed past the check and failed several steps later inside a git fetch with a
much worse message. It now probes with `docker version --format
{{.Server.Version}}`; `docker info` is unusable here because **it exits zero
even when the server half fails**. Both a zero exit and a non-empty server
version are required, with a parametrised test over all four combinations.
`check_daemon=False` skips the subprocess where the answer is only advisory.

**Not built on purpose:** no model-facing path. Nothing yet hands the catalogue
to a model or lets an orchestrated plan call a tool. Storage and isolation
should be solid before anything automated can reach them.

### Sandbox isolation — built (2026-07-31), salvaged not written

`agent/off-crm-v0-12-ai-studio` — an abandoned parallel design from 24 July —
had already solved container isolation before the `ai/` module existed. Rather
than merge that branch (14 conflicts, and it carries a whole second AI module
with no `ai/` at all), the isolation layer was lifted into `ai/sandbox.py`.

- [x] `docker_command()` — `--network=none`, `--read-only`, `--cap-drop=ALL`,
      `--security-opt=no-new-privileges`, `--user=65534:65534`, pids/memory/cpu
      caps, and `noexec,nosuid` scratch space.
- [x] **`--pull=never`**, the sharpest idea in the original: the image must
      already be present. Without it, a crafted image name *is* a network fetch
      — a way to reach the internet from the one feature that must not.
- [x] **Improved on the original:** `--memory-swap` equal to `--memory`. Without
      it the memory cap is advisory, since a container can exceed it by
      swapping. The salvaged version omitted this.
- [x] Images must be **version-pinned**; `:latest` is refused, because the image
      you reviewed is then not necessarily the image that runs. Image names are
      validated against a strict character set so a name cannot smuggle extra
      arguments into the docker invocation.
- [x] Workspace is `inbox/` (read-only), `work/` (writable) and `store/` —
      which is **not mounted at all**. Not read-only: absent. The context layer,
      recall index, egress log and encrypted keys do not exist in the
      container's view of the filesystem.
- [x] Sandbox jobs are `DataClass.PUBLIC` only, enforced. Anything carrying a
      person belongs on the egress path where the tier rules apply.
- [x] Refuses rather than degrading: Render and other nesting hosts are detected
      up front, and a missing Docker is a refusal, not a fallback. Python cannot
      sandbox Python, so there is no weaker option worth offering.
- [x] Disk budget counted by off_CRM (10 GB default), because Docker cannot
      size-cap a bind mount. Documented as a safety limit rather than a lock.
- [x] **§5.12(c) now covered.** Composition is asserted on every invocation, and
      a live test starts a real container and tries to open a socket — skipped
      unless `OFF_CRM_SANDBOX_TEST_IMAGE` names a pre-pulled image, since
      `--pull=never` forbids fetching one and a network-isolation test that
      quietly downloads from the internet would be self-defeating.

**Still unverified:** the flags themselves need a real Docker daemon. Everything
around them is tested; run the live test on your machine to close that.

### Verify loop — built (2026-07-31)

Where the quality per credit actually comes from. Not models voting: a cheap
model writes, **code** judges, the specific failures go back, and a more trusted
model reads the result. Checking is easier than producing, and output tokens
cost several times what input tokens do, so the checking half is the cheap half.

- [x] `ai/verify.py` — `VerifyLoop`: generate, check, repair, optional review.
- [x] **Enforces the same checks the eval harness scores with.** `checks_for()`
      reads the suite's `default_checks` from `config/evals.yaml`, so what
      production enforces and what the harness measures cannot drift apart —
      one edit moves both.
- [x] **The best attempt wins, not the last.** A model told to fix a length
      problem will cheerfully break the subject line; returning the final
      attempt would ship that. Ties go to the earlier round, since a later round
      that only matched it cost money for nothing.
- [x] **Deterministic checks are the gate; a model review only advises.** A
      glowing review cannot turn a failing draft into a passing one — tested.
- [x] Round cap: default 3, hard cap 5 regardless of what a caller asks for.
      Rounds 1-2 capture most of the available gain, and a loop that can run
      twenty times is a way to spend twenty times the money on a task that is
      not converging.
- [x] A policy refusal **stops** the loop rather than retrying it. Retrying
      produces the identical refusal.
- [x] No checks supplied means nothing was verified, and it says so rather than
      reporting a pass.
- [x] The repair prompt carries the previous draft in `instructions`, not
      `prior_drafts` — so a tier C model can fix its own work without the
      payload widening to carry campaign material. Tested: a repair round to a
      restricted provider stays pseudonymous and never gains the template.
- [x] The reviewer prefers a **second opinion within the same tier**, never
      dropping a tier to find one. Self-review is labelled as such.
- [x] Shipped as a fourth run mode, `verified`, so the eval harness can score
      it against the champion. The API dispatches it explicitly rather than
      letting it fall through to `simple`.

### Recall over sent mail (RAG) — built

Retrieval where the access rules, not the search, were the work. A normal RAG
stack leaks in four places; each is closed by construction here.

- [x] `ai/recall.py` — local full-text search (SQLite FTS5) over the owner's own
      sent mail. **No embeddings, no API key, no network call.** Indexing the
      whole archive posts nothing to anyone and works offline.
- [x] **Redacted before it is stored, not on the way out.** Most stacks keep the
      raw text and clean it at query time, which makes the index the most
      dangerous file in the product. Here names, companies, addresses, phone
      numbers and links are removed before the write. A test reads the raw bytes
      of the database file and asserts no identity survives in it.
- [x] Redaction is **targeted, not guessed**: off_CRM knows exactly who its
      contacts are, so it deletes their names precisely. The vocabulary covers
      *every* contact, not just the recipient — an email to one person routinely
      names another. A pattern pass then catches what no contact list could know.
- [x] Over-redaction is the deliberate choice where the two disagree. A common
      first name is removed even though it costs a legitimate word sometimes.
      Dates are kept: a date identifies nobody and losing them makes the
      snippets useless.
- [x] **Sent mail only, enforced twice.** `index_message` refuses an inbound row,
      and `store.sent_messages` filters to outbound in the SQL with no parameter
      that could switch it.
- [x] **Quoted threads are cut off first.** A follow-up usually quotes the reply
      underneath it — that block is *their* mail inside *your* mail, and it never
      reaches the index.
- [x] **No model can search it.** No tool, no function, no retrieval interface,
      no provider import, no network import. off_CRM chooses the search, reads
      the result and pushes a payload. Asserted structurally.
- [x] Snippets leave as `DataClass.CAMPAIGN` — the honest label for the owner's
      own business writing. Calling it `public` would have smuggled it past the
      rule keeping campaign material from restricted providers. **Two
      independent barriers, neither special-cased for this feature:** tier C and
      D refuse the class outright, and the snippets travel as `prior_drafts`,
      which a `minimal` policy does not carry at all.
- [x] The payload is still scanned on the way out, so a regression in redaction
      blocks the call rather than leaking.
- [x] Wired into the live send path and the unattended sender. A reply sets a
      "this one worked" flag and is otherwise not stored, which makes
      "show me emails like this that actually earned replies" possible.
- [x] Deletion: forget one message, forget one person, or clear everything.
      Redaction is not an answer to a deletion request.
- [x] Past emails screen: search, and a preview that renders the **real**
      outbound payload rather than a description of it.

### Orchestration audit (2026-07-31)

Full design review in `docs/architecture/`. Two defects found and fixed; both
reproduced against the real code before changing anything.

- [x] **Simple mode never picked the cheap model.** `candidates_for` returns
      permitted pairs cheapest-first, then `broker.plan` discarded everything
      below the top tier — so with Mistral (A, cost 20.0) and DeepSeek (C, 3.57)
      connected, a `public` coding task ran on Mistral at **5.6x the cost**,
      while the free model that was fully permitted sat idle. The same-tier rule
      exists to stop *failover* demoting restricted data; it was also gating
      *initial selection*, which is a different thing — `candidates_for` has
      already checked `permits(data_class)` on every candidate, so picking a
      cheaper one is not a demotion. Narrowed to: `public` uses the full
      cost-sorted list across tiers, everything else keeps the old behaviour.
      Each candidate still builds its own payload under its own policy.
      Switchable per workspace via `cross_tier_public_routing` (default on).
- [x] **`best_text` did not mean best.** It returned `branches[0]` after a sort
      on `(tier, ok, duration_ms)` — the fastest reply from the highest tier, not
      the best answer. Nothing scores quality; no scorer exists. The docstrings
      were honest (compare mode says the *owner* picks) but the name promised a
      judgement, and it ships through `to_dict()` into `frontend/src/types.ts`.
      Renamed `first_permitted_text`; `best_text` kept as a deprecated alias so
      the API contract is unchanged. A real `best_text` can land with the evals.
- [x] The Simple mode UI description claimed "cheapest" unconditionally. Now
      states the actual rule: cheapest for public work, most-trusted for person
      and campaign data.

### Notebook export (§4G, 2026-08-10)
- [x] `notebook.py` + `offsetx-notebook` (`targets`, `plan`, `export`).
      Docs: `docs/architecture/NOTEBOOK_EXPORT.md`.
- [x] **NotebookLM has no public write API**, so this produces a bundle you
      upload by hand rather than an integration that would break the week
      Google moves a button. The same bundle suits a Claude Project, a ChatGPT
      Project, or a notebook you host.
- [x] **The destination is a trust tier.** An export you drag into NotebookLM
      is a push, and the rules do not care that the transport is a person.
      `notebooklm` is C (Google free tier, terms permit training on input),
      `hosted_notebook` B, `self_hosted` A. Raising a tier needs a written
      reason; lowering one does not.
- [x] Built from a declared allowlist of sections, each naming its data class.
      The tier decides which survive; a withheld section's data is never even
      fetched.
- [x] Scanned with `ai/scanner.py` before the first byte reaches disk. A hit
      blocks the whole export and leaves no folder behind — a partial bundle is
      worse than none, because it is uploadable.
- [x] Every withholding is written down with its reason and its fix, in the
      README and `MANIFEST.json`. Nothing is silently absent.
- [x] **Mailbox content is unreachable structurally**, not by a runtime check:
      no section carries the class, and a test pins the exact set of store
      methods this module may call. `sent_messages`, `last_outgoing` and
      `record_reply` are not in it.
- [x] Addresses never appear at any tier, including `full`.
- [x] Below `minimal`, people and companies are tokenised **per bundle**
      (`PERSON_1..PERSON_n`) — one shared token for 200 people is a list with
      the answers removed. Free text is scrubbed too, so a public hook reading
      "Ana Silva spoke at the EU trade summit" survives as "PERSON_1 spoke at
      the EU trade summit". The campaign's own name is withheld below `minimal`
      as well: it is usually the ICP written out.
- [x] The map back to real people is written **outside** the uploaded folder,
      at `0600` — not a warning inside it, because "select all and upload" is
      what people actually do.
- [x] **Does not assume email.** Sections declare campaign kinds; outcomes and
      templates are email-only and refuse by *kind*, not by tier, so the owner
      is not sent looking for a permission problem that does not exist.
      `campaign_kind()` reads a `kind` column that does not exist yet and falls
      back to `email`; a test asserts the column is still absent, so the day it
      lands the test points at the reader that needs checking.
- [x] No model touches a bundle. An AST test fails the build if this module
      ever gains a route to a transport.

### Browser agent, Stage 1 — off_CRM gets hands (2026-08-18)
- [x] **The blueprint first.** `docs/architecture/BROWSER_AGENT_BLUEPRINT.md`
      maps every Strawberry feature the owner listed onto eight stages, and says
      honestly which are already built here under other names — model routing,
      memory, credits, local-first, routines and the permission substrate all
      exist. The genuinely new work is the browser, the run loop, companions,
      skills, MCP and the crawler.
- [x] **No Chromium fork, and the reason is written down.** A fork buys one
      thing: the agent runs in your real session. The same property comes from
      launching *your* browser against *your* profile with a debugging port and
      driving it over CDP. What it does not buy is an app with your name on the
      icon — stated rather than glossed.
- [x] **A hand-written CDP client**, for the reason the WebM muxer is
      hand-written. Playwright's value is launching browsers and we are
      attaching to one that already exists; it would add ~300MB of browsers we
      would never run.
- [x] **The accessibility tree, not the markup.** A fiftieth the tokens, stable
      across restyling, and expressed in the vocabulary instructions are written
      in. Every actionable node gets an integer; **a model names a handle and
      cannot describe an element**, which is the same closed-vocabulary rule
      `ai/tools.py` applies to Docker.
- [x] **Ten verbs and no `evaluate`.** If a model could supply JavaScript to run
      in a logged-in session, the policy layer would be the only thing between a
      prompt injection on some page and the owner's Gmail — and the open web
      will eventually serve one.
- [x] **Real input, not JavaScript shortcuts.** `Input.dispatchMouseEvent` and
      real key events, because a synthetic click skips the hover, focus and
      pointer handlers many sites depend on, and an assigned field value looks
      filled and behaves empty.
- [x] **The policy layer is the honest part.** `discovery.py` blocks LinkedIn,
      Instagram and the rest for its *headless* engines and that stays. Driving
      your own logged-in session is a different act, so it gets a different
      policy — drawn at **volume and autonomy** rather than at domain: reading
      pace on session-gated platforms, and **attended-only**, so the agent goes
      there when asked and never on a schedule. localhost, `.internal` and the
      cloud metadata endpoint are refused outright.
- [x] **An append-only trace.** No delete, no edit, no truncate — an audit log
      with an eraser in it is not one. It is also what makes a run resumable and
      what drives the watch-it-think view: one artefact, so the thing you watch
      and the thing you audit cannot disagree.
- [x] **Three real bugs found by running it.** `select` was advertised and never
      implemented; CDP's node list is not document order, so the first snapshot
      read the page out of sequence; and thirteen Chromium processes leaked per
      run because `start_new_session=True` makes the browser its own
      process-group leader and `terminate()` never reached the renderers. The
      last one presented as flaky tests, which is what a resource leak usually
      presents as.
- [x] **Verified against Chromium 141**, not a mock: navigate, perceive, type
      with real keys, re-read the field from the browser, refuse an unconfirmed
      send, send, read the page's own output, screenshot with a real PNG header,
      choose a dropdown by its visible label with the `change` event firing, and
      refuse a handle nobody issued.
- [x] 32 browser tests, 3 of them live. **1,415 Python tests**, 0 leaked
      processes.

### Stage 7a — the posting-rate control: your cap, the engine's advice (2026-08-18)
- [x] **The owner's answer changed the design.** Asked for a daily posting
      ceiling, the owner said: *"it should be left up to the user, he will
      decide, although the AI will make him the ideal recommendation after
      looking at the data."* That is a better shape than a number, and it is
      what got built.
- [x] **A cap per handle.** `dist_accounts.daily_cap`, set by the owner, checked
      when a post is scheduled, counted **across every campaign** — the handle is
      what gets restricted and it does not care which campaign filled its day.
      It sits under the platform's published limit, under the pacing arithmetic
      and under any goal.
- [x] **Zero means no cap, not zero posts.** Nothing invents a default: a number
      this code made up would be a limit the owner never chose being enforced as
      though they had. With none set, the platform's own limit still binds.
      Reconnecting an account does not reset it either.
- [x] **A campaign's ceiling is the sum of its accounts' caps**, because the rate
      is one campaign-wide number and three handles capped at two can carry six
      between them. One uncapped account means the campaign has no cap — summing
      over a partly-capped set would invent a limit out of handles left open.
- [x] **The pacer recommends and waits.** `auto_pace` became `pace_mode` with
      three values: `off` (nothing runs), **`suggest`** (the number is worked out
      every cycle and applied by nobody — the new default), `auto` (it moves
      itself, still never past the cap). The same shape the video review queue
      has, for the same reason: a machine that makes things unattended must not
      also decide they go out.
- [x] **`accept` or `dismiss`, not a number.** `POST /content-automation/pace`
      takes a word, because setting the rate is a `PATCH` and this is a different
      act — a person answering something the machine asked. A suggestion is only
      stored when it differs from what is running; a screen that repeats itself
      hourly is one people stop reading.
- [x] **The old boolean still means what it meant.** `auto_pace: true` reads as
      `auto`, `false` as `off`, so no existing install changes behaviour because
      the default did. There is a test for exactly that.
- [x] **A UI, because a cap you can only set with curl is not the owner's.** New
      **Posting** screen: a cap box per handle, the three modes with their
      consequences in words, and the waiting suggestion with its reasoning and an
      Accept button.
- [x] **Verified on a live server.** A handle capped at 2 took two posts for one
      day and refused the third by name; the next day was fresh; with 20 real
      published posts at 1,000 views each against a million-view goal 100 days
      out, the engine wanted **9.80/day**, ramped its suggestion to **1.25/day**,
      and a cap of 1 pulled that to **1.00/day** with *"Capped at 1.00 a day by
      your own cap. Raise it if you want the goal met sooner."*
- [x] **What is still blocked on the owner, and only this:** no platform app
      approvals have been started. YouTube is the one reachable adapter and needs
      a Google Cloud project with the Data API enabled. Nothing else waits.
- [x] 19 pacing-cap tests, 6 rewritten automation tests. **1,383 Python tests,
      115 frontend**, build clean.

### Stage 6 — the effect engine: 48 primitives, 124 looks (2026-08-18)
- [x] **The largest part of an editor, made searchable.** CapCut's eight hundred
      filters written as eight hundred implementations are eight hundred things
      nothing can rank. `video/effects.py` declares **48 pixel operations** and
      **124 looks over them**; `frontend/src/video/shaders/` implements the
      operations in GLSL. A new look is one row. Feature map 54 → **61 built**,
      45% → **52%** of the reachable rows.
- [x] **A look is an ordered stack, not a knob.** `noir` is a desaturation, a
      contrast, a vignette and a grain — in that order, because they do not
      commute. So a preset is a list of `(primitive, params)` and the renderer
      runs it as a chain of full-screen passes, ping-ponged between two textures.
- [x] **Every look gets a strength slider for free.** Each parameter declares
      the value at which its primitive does *nothing*; applying at `amount`
      interpolates from there. Colours and structural choices — a mirror's axis,
      a kaleidoscope's segment count — declare no neutral and do not
      interpolate, because half a fold is a different picture and not a weaker
      one.
- [x] **The server resolves; the browser executes.** The manifest carries each
      clip's stack already flattened into passes. Deliberately the opposite of
      how a transition works, and for a reason worth writing down: a transition
      is one row, a look is a stack drawn from a hundred-odd of them, and nobody
      should download the catalogue to draw one clip. It also means **a look
      nobody declared cannot reach a shader**.
- [x] **Seven controls that were declared and never drawn.** `PROPERTY_SPEC` has
      carried `tint`, `sharpen`, `grain`, `vignette`, `corner_radius`,
      `border_width` and `shadow` since the timeline was written — stored,
      clamped, animated, and drawn by nothing, because a 2D canvas cannot. All
      seven are primitives now, and `temperature` stopped being a sepia wash
      plus a hue rotation and became the red/blue rebalance it always claimed.
- [x] **Nothing is random.** Grain and noise seed from the *frame index*, never
      the clock. A preview and an export that disagreed about the grain would be
      two different videos, and a re-export has to produce yesterday's file.
- [x] **A machine with no WebGL2 still exports**, falls back to CSS filters, and
      **names what it lost** per clip rather than handing back a picture that is
      quietly wrong.
- [x] **A test reads the other language.** Every primitive must have a shader and
      every shader a primitive, with parameter names matching in both
      directions — parsed out of the TypeScript, because nothing else would
      notice a rename on one side.
- [x] **Two real bugs, both found by running it.** `edge` took a parameter called
      `mix`, which shadows the GLSL builtin and compiles right until something
      below it calls `mix()` — there is a test for that class now. And
      `posterize` neutralised at 64 levels, so a preset containing one was not
      *quite* a no-op at strength zero; its neutral is 256 and the drift over the
      whole catalogue is now 0/255.
- [x] **Verified against real pixels, not assertions.** Headless Chromium on
      ANGLE/SwiftShader compiled all 48 programs; nineteen exact predictions
      computed in Python matched the GPU (invert, one stop of exposure, Rec.709
      luma, the sepia matrix, a 120° hue rotation, chroma and luma keys to alpha
      0, a blur turning a hard edge into 99/156/166); **all 124 looks at
      strength zero drifted 0/255**; and `paintFrame` itself put `mono` on a
      clip at `[119,119,119]` and darkened a vignette's corner from 255 to 110.
- [x] 49 effect tests and 19 frontend tests. **1,358 Python tests, 115
      frontend**, build clean.

### Stage 5e — the review queue: push, ignore, edit (2026-08-18)
- [x] **The gate between a machine that makes videos alone and an audience.**
      Every assembled or directed project now lands in a queue by itself, and
      nothing leaves it except through a person pressing push or ignore. The
      button the owner asked for early and video never had. Feature map 53 →
      **54 built** of 162; still 45% of the reachable rows.
- [x] **Two verdicts, three buttons.** Push and ignore are the answers; *edit*
      is what you do before answering. There is deliberately no stored `edited`
      flag — it is `project.version != baseline_version`, a question the
      document already answers. A flag written at edit time goes stale the
      moment somebody undoes back to the start.
- [x] **Push requires a passing export of *this* version.** What distribution
      publishes is bytes, not a document. Without the "of this version" half the
      common accident is fatal: export, keep editing, push, and publish a video
      the owner is no longer looking at. Three refusals, each a sentence the
      owner can act on: never exported / gates failed / edited since exported.
- [x] **The diff is measured on both verdicts and stored with them.**
      `assembly.difference(baseline, current)` — the learning signal starts
      collecting the day the queue exists. An owner who pushed something
      untouched approved of the assembler; one who rebuilt half of it first said
      something far more specific, and named the clips. An ignore after twenty
      minutes of editing is a different verdict from one on sight.
- [x] **The baseline is copied into the review, not looked up later.**
      `video_history` is capped at 300, so a project worked on for an afternoon
      loses the very version the machine produced. There is a test that edits
      past the cap and proves the diff still means what it says.
- [x] **A verdict is given once**, in the engine and again in the store beneath
      it. A number that moves when you click twice is not a score. One *open*
      review per project is a partial unique index in SQLite rather than a
      check-then-insert two requests can both pass; a project ignored and later
      re-cut can be sent back, and both verdicts are kept.
- [x] **The handoff is real, and cost one function.** `GET
      /campaigns/{id}/video-approved` answers what
      `/image-assets?status=approved` answers for pictures, with the same row
      shape. The API's asset resolver tries the image store then the render
      store, so a post carrying a render id publishes the video and the
      publisher learned nothing. A render that **failed its gates is not
      resolvable** — posting one would walk around the checks.
- [x] **A real bug fixed on the way.** `difference()` computed
      `kept = |old ∩ new| - moved - removed`, but removed clips are already
      outside the intersection, so every one was counted twice and `kept_share`
      understated what survived — the exact number this queue makes a headline.
      Four clips, one removed, one trimmed read 0.25 instead of 0.5.
- [x] **Verified on a live server, not only in tests.** Real uvicorn, real
      SQLite: an assembled project appeared in the queue by itself marked
      not-ready with its sentence; push before an export → 422 *"Nothing has
      been exported yet"*; an edit after one → *"This has been edited since it
      was last exported"*; re-export → push with `kept_share 1.0`; the render
      under `/video-approved`; a post pointing at it published with **the
      video's own bytes** in the outbox, compared byte for byte; a second
      verdict → 422.
- [x] 37 review tests and 1 assembly test. **1,309 Python tests, 96 frontend**,
      build clean.

### Stage 5d — the director: a topic in, a finished project out (2026-08-16)
- [x] **The model half.** `POST /campaigns/{id}/video-projects/direct` takes a
      topic and returns a stored, renderable project. The model chooses the
      shape and writes the words; the assembler does everything else. Feature
      map 52 → **53 built**; "Script → video, auto-assembled" is now ●.
- [x] **A model asked to emit a timeline emits invalid ones**, and nobody can
      review four hundred lines of JSON before they become a video. A model
      asked to pick one of eight declared ids and write three sentences is doing
      a job it is good at, and the answer is small enough to check completely.
      So `director.py` is almost entirely the checking.
- [x] **The reply is untrusted input.** A shape nobody declared is refused by
      name with the real list; prose is refused rather than guessed at; a fence
      is unwrapped (they all do it); a sentence before the JSON is read past; a
      length outside the bounds is clamped and said so; forty lines are cut to
      what the beats hold; a 400-character caption is trimmed; an invented field
      is ignored and named. Twenty of the thirty-one tests are that list.
- [x] **A hostile topic cannot do much, and that is architectural.** Topics come
      from scraping, so a trend title can say anything — including instructions
      aimed at whatever reads it next. The reply is validated against a closed
      set, so the worst it achieves is a video in a *different one of the eight
      declared shapes*. There is no field it can fill with an arbitrary edit and
      no path from the reply to a file. A test proves it with a real injection
      string.
- [x] **The prompt lists the real recipes**, read from the registry at call
      time. One naming a shape the assembler does not have produces a refusal
      nobody can act on; one missing a shape never offers it.
- [x] **Data class `public`, not `campaign`.** A topic is usually a trend title
      that was already on somebody else's website, and calling it campaign
      material would narrow the tier rules for something already public.
- [x] **Two real bugs found by running it.** `DirectionRefused` was a plain
      `ValueError`, so a model picking a bad recipe would have returned a 500
      instead of the sentence — it is a `TimelineError` now, like every other
      refusal. And the new endpoint did not catch `NoPermittedProvider`, so the
      very first thing anyone hits — no provider connected — was a stack trace
      instead of the 409 that says to open Connectors.
- [x] **Verified end to end.** Topic `"why nobody reads changelogs"` → the model
      picked `pattern_interrupt`, wrote three lines, asked for 12s → assembled
      over two real VP9 shots and a WAV bed → **`renderable: true`, no
      warnings**, one note about the music being shorter than the video.
- [x] 31 director tests and 6 engine tests. **1,266 Python tests, 96 frontend**,
      build clean.

### Stage 5c — the assembler: material in, finished timeline out (2026-08-16)
- [x] **The line the whole editor was cut from.** `POST /campaigns/{id}/video-
      projects/assemble` takes a recipe and a length and returns a whole project
      — cut, animated, captioned, scored — that the gates accept with nobody
      having touched a timeline. Blueprint Stage 5's centre; feature map 49 →
      **52 built**, 42% → **45%** of the reachable rows.
- [x] **A model picks the recipe and writes the words; it never builds the
      timeline.** The decision everything else follows from. A model that emits
      a document emits invalid ones — overlapping clips, transitions that do not
      fit, footage read past its end — and every invariant this project enforces
      becomes a suggestion. Choosing from a declared list is what a model is
      good at and what can be checked. Assembly is arithmetic and runs with no
      model at all.
- [x] **Nothing constructs a clip.** Every piece goes through the same `edits`
      functions a person's clicks do, so an assembled project is valid for the
      same reason a hand-made one is. If the assembler could produce an
      overlapping timeline, so could a user, and the invariant would already be
      broken.
- [x] `video/recipes.py` — **8 shapes over 5 families** (`hook`, `list`,
      `story`, `montage`, `demo`) as rows: beats with shares, and which
      animation, speed curve and text style each beat uses. Shares are fractions,
      so one recipe fits any length. A test resolves every preset id a recipe
      names — one pointing at an animation nobody declared is one that fails on
      the video somebody actually wanted.
- [x] **The duration is exact, at every recipe and every length.** The export
      gate compares a file against the project's own length, so a 30s target
      produces exactly 30s — snapped to a whole frame, the last beat absorbing
      what the shares round away. 48 parametrised cases assert it.
- [x] **The material decides the cuts, inside what the recipe asked for.** A beat
      longer than one clip can stretch to gets more cuts whatever the recipe
      wanted; ten times its own length is as far as one goes. 300s from 1s of
      footage cuts itself 31 times and still lands exactly.
- [x] **Short footage is slowed, not gapped** — 2s over a 6s beat plays at 0.37x,
      reading all its material and none past the end. The rate rounds *down* to
      four places: rounding the last one up makes a clip consume ticks the source
      does not have, which the assembler found by refusing itself.
- [x] **It says what it settled for.** Music shorter than the video, a curve a
      clip has no material to spare for, a line nobody could read in the time it
      is on screen — each a sentence in `notes`. The readability rule is the
      caption engine's own `READABLE_CPS`, not a second copy of it.
- [x] **`difference(before, after)` — the edit-diff.** What was added, removed,
      moved, retimed, restyled and rewritten, and what share of the assembly
      survived. Deliberately coarse. A person who accepts a cut says nothing; a
      person who moves it says something specific, and this is the only place
      that gets written down — the signal any later "learn from what gets edited"
      has to be built on, worth having before there is anything to learn.
- [x] **Verified end to end, for real.** The server assembled a project from
      `setup_turn_resolve` over two real VP9 shots and a WAV bed; its manifest
      came back `renderable: true` with no warnings; Chromium exported that exact
      document and the file went back through the server's gates: **all eight
      passed** — `1080x1920 video/webm, 8.00s`, six footage clips drawn, an Opus
      track. ffmpeg reads it as `vp9 30fps / opus 48000 Hz stereo`.
- [x] **A real gap that run found:** a bitstream the decoder rejects — a file
      that demuxes cleanly and names a supported codec but whose frames are not
      what its header says — used to take the whole render down with it. It now
      costs its own clip, draws the hole the painter already draws for a missing
      asset, and is reported once per file however many clips use it.
- [x] 93 assembly tests and 5 engine tests in Python, 1 regression test in the
      browser. **1,229 Python tests, 96 frontend**, build clean.

### Stage 5b — time remapping: curves, freeze, reverse (2026-08-16)
- [x] **Three menu items, one integral.** Freeze frame, reverse and speed curves
      are all the same question — how a clip's offset maps to a position in its
      material — so they are one function, `Clip.source_at`. At a constant rate
      it is `offset × speed`, which is why the conformance frames came out
      unchanged when it landed. Feature map 44 → **49 built**, 38% → **42%** of
      the reachable rows.
- [x] **`consumed(t)` is the area under the speed curve**, and the curve is
      straight between its points. CapCut's are bezier; these are not, on
      purpose. The resolver exists twice and the two copies have to agree *to
      the tick*, and a trapezoid — `(v₀+v₁)/2 × Δt` — is the same arithmetic on
      the same doubles in both languages where a cubic is not. An eased speed
      point is refused, and the message says to use more points instead.
- [x] **A speed of zero is a freeze, not a missing value.** That is what lets a
      frozen stretch live *inside* a curve, which is what every "bullet time"
      preset is. Two places had to stop writing `float(speed or 1.0)` — the
      third sighting of the falsy-zero bug that once restarted a paused campaign,
      and the first one caught by a test written before the code.
- [x] **`freeze_frame` is three edits in a coat**: split at the playhead, open a
      gap, drop in a clip at speed 0 reading the instant that was on screen. It
      inherits the *resolved* properties of that instant, so a clip caught
      mid-zoom holds the size it was at rather than snapping back to defaults.
- [x] **Reverse is a flag, not a negative speed.** A negative speed makes every
      other piece of arithmetic in the timeline signed for the sake of one clip.
- [x] **12 speed presets over 4 families** — `ramp`, `hero`, `impact`, `loop` —
      as rows, the same shape as transitions and animations. Each carries its
      `average`, which is the number that decides whether a clip still fits in
      its source: `hero` averages 1.10×, so a ten-second clip on one needs eleven
      seconds of material. `keep_duration=False` divides by that average to find
      the length at which the curve consumes what the clip consumed before.
- [x] **Retimed sound is left out and the manifest says which clips and why.**
      Resampling audio is not playing it faster, it is deciding about pitch.
      Playing a clip's audio at one rate under a picture doing something else
      drifts further apart the longer it runs, so `retimed_reason` names the clip
      and the mix goes on without it. Both languages carry the rule and the
      conformance fixture pins the answer.
- [x] **A bug only a real browser could find.** The exporter samples the middle
      of an output frame, and it did that by adding `half a frame × clip.speed`
      to the resolved source time. Wrong twice over once time is remapped: a
      reversed clip moves *backwards*, and a curved clip's local rate is not its
      `speed` field. It now resolves a second frame half a step later and takes
      source times from that — while still drawing the cast of the first,
      because at a cut the two hold different clips.
- [x] **Verified against the server's own prediction.** Python resolved a `hero`
      curve, a `bullet` freeze and a reverse and wrote down the source tick it
      says belongs on each of thirty output frames; Chromium ran the same
      documents through its resolver, decoder and painter over the 60-frame test
      video. **All ninety source ticks identical, every drawn frame matching** —
      `bullet` holding frame 15 for eight output frames, `reverse` counting 29
      down to 0 with nothing repeated. The first run is what found the off-by-one.
- [x] The conformance document now carries a clip that is both on a `hero` curve
      and reversed, with four sample ticks across it — time remapping is the one
      place a clip's source time stops being a multiple of its offset, so an even
      spread there would prove nothing.
- [x] 34 retime tests in Python, 11 in the browser, plus a regression test for
      the sampling bug. **1,130 Python tests, 95 frontend**, build clean.

### Stage 5a — video on the canvas (2026-08-16)
- [x] **Imported footage draws now**, in the preview and in the export. Until
      today a video clip's sound worked and its picture was a red hole, and the
      manifest refused to call any project with footage on it renderable.
      Blueprint Stage 5, first half; feature map 43 → **44 built**.
- [x] **`paintFrame` needed one line.** Its `AssetSource` is a
      `CanvasImageSource` and a `VideoFrame` is one, so the painter could always
      draw a frame — what was missing was anything that could produce *the frame
      at a given instant*. The one line is that a clip's own table entry wins
      over its asset's: a still is shared by every clip that places it, a piece
      of footage is at a different moment of itself in each.
- [x] **A demuxer, written by hand, for both containers.** `demux/matroska.ts`
      walks EBML into Clusters and reads SimpleBlocks; `demux/isobmff.ts`
      expands MP4's five parallel sample tables — `stts`, `ctts`, `stss`,
      `stsc`, `stsz`/`stco` — into one flat frame list. One level deeper than
      `video/gates.py`, which already walks both formats to read a file's shape.
- [x] **Not a `<video>` element**, which reads as simpler and is worse three
      ways: a seek costs tens of milliseconds and an export asks for every frame
      in order, so a sixty-second render pays a minute in seeks; it needs a
      document, so no worker and no `OffscreenCanvas`; and it gives no way to
      *hold* a decoded frame, which is what freeze frame and reverse are made of.
- [x] **Forward-only decoding with a cursor.** An export asks in increasing
      order, so the cursor never goes back and every frame is decoded exactly
      once. A backwards jump or a jump into another group of pictures restarts
      from that group's keyframe — what a seek costs in any editor. Twelve
      frames cached, and clips that leave the screen give their decoder back.
- [x] **Decode order is not presentation order.** The frame list stays in decode
      order because that is what a decoder must be fed, and a separate index
      sorted by presentation time answers "which frame is showing at T". The MP4
      fixture carries a signed `ctts` so the two genuinely differ.
- [x] **A real bug real Chromium found: a flushed decoder will not take a delta
      frame.** `decodeQueueSize` falls to zero when a chunk is *accepted*, long
      before its frame comes out, so treating that as "done" flushed on the
      first frame of every file and then refused the second. The pump now waits
      for output to stop arriving before it concludes anything.
- [x] **A second real bug, found by measuring: an output frame is an interval,
      not an instant.** A container stores times in its own units, so 30fps
      footage has frames at 33ms and 67ms while a 30fps timeline asks at 33.333
      and 66.667. Sampled at the leading edge that asks for frame 1 twice and
      never asks for frame 2 — a third of the footage silently replaced by
      duplicates. The exporter samples half an output frame ahead, at the middle
      of the interval the frame covers. The measurement read `0,1,1,3,4,4,6,7,7`
      before and `0,1,2,3,4,5,6,7,8` after.
- [x] **Verified in a real browser, and measured.** Chromium encoded a real
      60-frame VP9 file where frame *n* is a flat colour spelling *n* out as a
      three-digit base-4 number — levels 85 apart, so the dozen levels a lossy
      codec shifts a flat fill by cannot round a channel wrong. Demuxed,
      decoded, put on a timeline, painted, and the canvas's centre pixel read:
      **30 of 30 output frames matched their own source frame, in order, nothing
      duplicated and nothing dropped.** The export passed the gates and ffmpeg
      read it as `vp9 1080x1920 30fps, 2.00s`.
- [x] `scripts/build_mp4_fixture.py` — Python writes an MP4 from the spec with
      three different chunk sizes, sparse sync samples, a signed `ctts` and a
      version-1 `mdhd`, and the browser reads every frame's offset, length,
      keyframe flag and presentation time back exactly. The same cross-language
      check the WebM muxer already had, in the other direction.
- [x] **What the server cannot check, said plainly.** There is a gate for a
      missing audio track because a header says whether one exists. A clip that
      drew as a red hole produces a file whose header is perfect, so there is no
      equivalent — the browser reports per-file failures instead, and one
      unreadable import costs its own clip rather than the whole render.
- [x] 18 demux tests + 18 footage tests in the browser, 1 fixture guard in
      Python. **1,094 Python tests, 83 frontend**, build clean.

### Stage 4 — audio in the export (2026-08-16)
- [x] **Every file this project produced before today was silent.** The timeline
      had resolved gain per clip per instant since the day it was written and
      the exporter threw all of it away. Platforms bury silent video, so this
      was the difference between an export that can be posted and one that
      cannot. Blueprint Stage 4; feature map 40 → **43 built**, 38% of the
      reachable rows touched.
- [x] **A plan, not samples.** `video/mixdown.py` emits an *envelope* per clip —
      the points where its gain changes, in the clip's own time — and WebAudio
      applies exactly that shape with `setValueAtTime` /
      `linearRampToValueAtTime`. Asking the resolver per sample is 48,000 calls
      a second to produce a number that changes a few times across a clip, and
      would put a second mixer in Python that nothing ever runs.
- [x] **Dense only where the curve bends.** Between two keyframes the gain is a
      straight line. A fade is linear too — but it *multiplies* the volume
      curve, so a fade over a ramp is a parabola. Those stretches are sampled at
      100Hz and anything that turns out straight is collapsed back to its ends,
      each dropped point checked against the last *kept* one so a shallow curve
      cannot be walked away from one tolerance at a time. A constant clip is 2
      points; a one-second linear fade is 3; a two-second eased ramp is ~80.
- [x] **The gain rule now lives in one function per language** — `clip_gain()`
      in `timeline.py`, `clipGain()` in `resolve.ts` — called by both the frame
      resolver and the mixer. Two copies of it would be a preview that lies
      about the file it is previewing. The conformance frames came out
      byte-identical across that refactor, which is how we know it changed
      nothing.
- [x] **Footage is in the mix.** A video clip's sound travels in the same
      container as its picture and `decodeAudioData` reads it out. The picture
      still is not drawn; leaving the sound out because of that would be keeping
      the wrong half.
- [x] **Clipping is scaled, not clamped.** `headroom()` reports the worst-case
      sum at every envelope point — measured mid-crossfade, not at clip edges,
      because two clips fading through each other are loudest where neither
      starts nor ends. Over 1.0 the whole mix is scaled by the reciprocal, which
      keeps the balance between clips exactly, and the export reports that it
      happened. The manifest says it *before* the render, so it can be fixed
      properly instead.
- [x] **A new gate: `has_audio_track`**, asked for only when the server's own
      mix plan says the timeline makes a sound. A browser that cannot encode
      Opus hands back a perfect picture, and a silent video nobody noticed was
      silent is exactly this stage's failure mode.
- [x] `frontend/src/video/audio.ts` — the `OfflineAudioContext` graph, 20ms Opus
      frames, and a hand-written 19-byte `OpusHead` for when WebCodecs supplies
      no decoder description, because a WebM Opus track with no CodecPrivate is
      a file some demuxers refuse.
- [x] **Two muxer bugs found on the way in.** A cluster's Timecode is a whole
      millisecond, but block offsets were computed against the unrounded value —
      up to half a millisecond of error per block, which did not matter until
      there were two tracks to keep together. And a cluster only ended at a video
      keyframe, so a keyframe-sparse stretch could run past the 32,767ms a signed
      16-bit block offset can express; it now also cuts at 30s.
- [x] **Cross-language, both directions.** `npm run fixtures` now also writes
      `muxed_sample_audio.webm` carrying the real `opusHead()` bytes, and the
      Python gates read 48000Hz / 2 channels back out of it — the WebM prober
      learned `SamplingFrequency` and `Channels` to do it. The mix plan is in the
      conformance fixture's `mix` block and both planners are asserted to agree
      **point for point, including how many points**: the same curve described in
      a different number of points means one simplifier moved.
- [x] Deliberately not built: ducking, compression, EQ, normalisation, waveform
      display, beat detection. Each changes what the mix *sounds* like rather
      than what it *is*, and building them before the plain mix worked would mean
      debugging two things at once. The scoreboard guard asserts they are still
      marked not-built, in both directions.
- [x] **Verified in a real browser against a real tone, and measured.** A 3s WAV
      (440Hz left, 660Hz right) on a track with a one-second fade at each end,
      exported through headless Chromium and decoded back by Chromium's own
      demuxer and Opus decoder. ffmpeg reads the result as `vp9 1080x1920 30fps
      / opus 48000 Hz stereo, 3.00s`. Decoded RMS per quarter-second — 0.0623,
      0.1648, 0.2716, 0.3794, then 0.4310–0.4320 across the flat middle —
      against `A/√2·√((b³−a³)/3(b−a))` predicting 0.0623, 0.1648, 0.2715,
      0.3789, 0.4316. The fade came out of the file as the shape the planner
      described, and the channels did not swap on the way through.
- [x] 29 mixdown tests, 5 engine tests, 4 gate tests and 2 scoreboard guards
      in Python; 25 in the browser (11 mix conformance, 14 audio scheduling and
      OpusHead). **1,093 Python tests, 47 frontend**, build clean.

### Stage 2 — transitions, animations, the preset registry (2026-08-14)
- [x] `video/presets.py` + `frontend/src/video/transitions.ts`. **46 transitions
      over 9 families, 32 animations over 3, 12 text styles, 16 blend modes, 12
      more animatable properties.** Feature map: 29 → **40 built**, 37% of the
      reachable rows touched.
- [x] **Transitions without relaxing the invariant.** A dissolve needs both
      clips on screen and clips cannot overlap by a tick. The clips stay
      adjacent and a `Transition` on the track declares how far either side of
      the cut both are drawn — a bounded, declared property of the boundary
      instead of an accident of two clips' positions. Both sides share one
      `progress`; a clip drawn past its end is held at its last frame; one
      transition per cut; halves at both ends must fit inside the clip; an edit
      that destroys the cut removes the transition.
- [x] **Presets are rows, families are code.** A new transition is a line of
      YAML-shaped data, which is what makes the space searchable by the
      orchestrator later. `CAPCUT_TOOL_INVENTORY.md` argued this; this is it.
- [x] **An animation is ordinary keyframes**, so it survives a split, travels
      with a trim and resolves identically in both languages — none of which
      was rebuilt.
- [x] **A real bug found by the new tests: splitting inside a non-linear ease
      was not transparent.** The old resampler synthesised boundary keyframes
      from interpolated values, which is exact for a linear segment and wrong
      for every other kind — a sub-range of an ease-out curve is not an ease-out
      curve. The original split test passed only because it used a linear
      segment. Keyframes are now shifted rather than rebuilt: exact, and bounded
      by keeping only the nearest anchor either side.
- [x] Conformance fixture regenerated with a transition, a blend mode and an
      applied animation across it, and the TS test now asserts the transition
      field — the one place a clip is drawn outside its own bounds.
- [x] 36 new preset/transition tests, 3 regression tests for the eased split and
      trim, and the scoreboard guard now checks **both** directions: nothing
      claims to be built that is not, and nothing that shipped loses its mark.

### Goal-driven pacing (2026-08-14)
- [x] `distribution/pacing.py` — posting volume is adjustable **and the goal
      moves it**. `(target − measured views) ÷ views per post ÷ days left`, with
      every term checkable by hand. Blueprint §6.4.
- [x] **No data, no steering.** Below 5 measured posts there is no
      views-per-post figure, so it holds the declared rate and says why. A
      controller with nothing to measure is a random number generator, and that
      is the rule most likely to be broken by someone making it look clever.
- [x] **Raise slowly (+25%/cycle), lower immediately.** The errors are not
      symmetrical: a missed goal is recoverable next week and a banned account
      is not. An engine that notices it is behind and posts ten times more *is*
      a spam bot at that moment.
- [x] **10% deadband**, or the rate moves every cycle on noise and the schedule
      becomes unplannable. **Platform caps are hard** — Instagram's 25/day is a
      ceiling the arithmetic may approach and never cross, and the capping
      platform is named so a throttled campaign does not look like an
      under-performing one.
- [x] The new rate is stored, so the ramp compounds instead of restarting from
      the declared number every cycle and never arriving. `auto_pace` off by
      default.
- [x] A falsy-zero bug found by its own test: `float(x or 1.0)` turned a rate
      deliberately set to 0 — a paused campaign — back into 1/day.
- [x] 26 pacing tests + 8 in the automation cycle, including a live HTTP run
      against a real goal and 20 real metric rows: holds at zero data, then
      raises to a ramped 1.25 against a measured requirement of 9.8.

### Stage 1 — the content engine runs itself (2026-08-14)
- [x] `distribution/automation.py` — `ContentAutomationService`. Sweep → plan →
      draft → publish-due, on a timer, started and stopped with the app.
      Blueprint: `docs/architecture/CONTENT_ENGINE_BLUEPRINT.md` Stage 1.
- [x] **This was the highest-value missing line in the project.** Every piece of
      the content pipeline worked and none of them ran on their own; the Amul
      point in the brief is about time, and a trend acted on tomorrow is one
      somebody else already used.
- [x] **Which campaigns run is declared, not inferred.** The pipeline needs a
      distribution campaign *and* an image campaign, and nothing in the schema
      says which pairs with which. Guessing would post from the wrong brand, so
      the pairs live in the service's own config, a half-declared pair is
      dropped, and enabling with none declared is refused with a message.
- [x] **A failing step does not cost the cycle.** A YouTube quota error at the
      sweep must not stop posts a person already approved from going out. Each
      step is caught, recorded and reported; the next cycle tries again.
- [x] **The two human gates are untouched.** `publish_due` can only act on posts
      that already carry an approval. This service drives the machine either
      side of the swipe and the approval and stops at both.
- [x] The loop **waits before it runs**, so a restart loop cannot become a burst
      of sweeps against a quota. Interval clamped to 300s–24h.
- [x] Separate from the email `AutomationService` on purpose: that one is
      email-shaped, and nothing built from here may assume email.
- [x] `_TimerScope` — the four per-request engine factories read only
      `request.app.state`, so the timer passes an object with an `.app`. The
      alternative was changing thirty call sites to land in the same place.
- [x] 26 tests: declaration rules, corrupt-config safety, bounds, step order,
      per-step failure isolation, switch-off-by-name, no overlapping cycles,
      the wait-then-run loop, clean start/stop, and a live HTTP cycle through
      the app's real factories. Plus a structural test that this module imports
      no transport.

### Video projects on Postgres (2026-08-14)
- [x] `VideoStore` is opened through `resolve_target`, the same seam the egress
      log uses: explicit target, then `OFFSETX_DATABASE_URL`, then the local
      file. One variable moves timelines off a disposable disk.
- [x] The reason is not tidiness. `render.yaml` writes to `/tmp` on the free
      plan, and an instance that sleeps comes back empty — an hour of editing
      disappearing at that point is the work, not a storage detail.
- [x] **What it does not fix, stated rather than implied:** renders, uploaded
      recordings and generated pictures are bytes on a disk. The document is the
      part that took the work and the part that moves; files still need a real
      disk or object storage.
- [x] `tests/test_video_postgres.py` — 17 tests over **both backends**: schema
      creation, a whole edit session surviving a cold reopen with its undo
      history, undo/redo after a reopen, media and transcripts, the
      `ON CONFLICT ... DO UPDATE` upsert, the hash uniqueness that stops paying
      twice for one recording, and history trimming. Run against a real
      Postgres 16, not asserted.
- [x] A structural test parses `api/app.py` and fails if `VideoStore` is ever
      handed a bare path again — that mistake shows up only as work quietly lost
      on the next restart.

### Auto-captions (2026-08-14)
- [x] `video/captions.py`, `broker.call_transcript`, `OpenAITranscriptionProvider`,
      media import, and an **Auto captions** button. Docs:
      `docs/architecture/AUTO_CAPTIONS.md`.
- [x] **Half of it is a media import path, and that is not padding.** Nothing in
      off_CRM generates speech, so the caption button had nothing to listen to.
      `POST /campaigns/{id}/video-media` takes a voiceover or a clip, reads its
      header before storing anything, and refuses a file that does not declare
      its own length — a clip whose `source_duration` is a guess cannot be
      stopped from reading past its end. WAV is in for that reason and **MP3 is
      refused**: a WAV's length is in its header, an MP3's needs every frame
      walked. Uploading the same file twice returns the existing row.
- [x] **The scanner cannot read a waveform, and that changes the rules.** Every
      other egress path is protected by a pre-flight scan; a recording of
      somebody reading a customer list scans clean because there is nothing to
      read. So `TRANSCRIBE_FORBIDDEN_CLASSES` refuses `mailbox` and `internal`
      **by class, before a provider is looked up** — their protection *is* that
      scan. The tier filter still applies in full, the text part of the request
      is still built from the allowlist and still scanned, and the egress log
      records the size and word count but **never the audio or the transcript**.
- [x] **Word timings, not sentence timings.** A caption timed to a sentence
      appears in full before it is spoken. Three response shapes are read (flat
      words, words nested in segments, segments alone) and a segment-only answer
      is kept rather than refused.
- [x] **Where to break is deterministic, not a second model call.** Sentence end,
      then pause (>0.6s), then line length (42 chars), then maximum hold (5s). A
      comma only breaks once the line is over half full — breaking at every comma
      gives a stutter of two-word captions. A test asserts no word is lost
      between transcript and captions.
- [x] **The timeline's invariant is the specification.** Clips cannot overlap by
      one tick and speech does not respect that, so `lay_out` snaps to frames,
      holds each cue back from the next, stretches short cues only into the gap
      actually in front of them, and **merges a cue that cannot get one frame
      into its neighbour** rather than dropping a word.
- [x] Media time is mapped through the clip's start, `in_point` **and** speed, so
      captioning a trimmed clip captions what is left and a slowed clip stretches
      its captions with the speech. Both have tests.
- [x] **Captions are ordinary text clips** on a Captions track, so every existing
      edit works on them and a person reads them before publication — the same
      judgement the swipe and the post approval are. The whole set is one step of
      undo; running it twice replaces rather than stacks; new pictures never land
      on the caption track.
- [x] The transcript is stored per file and reused. Deliberately **not** the
      response cache, which refuses anything whose output is a message: a
      transcript is a fact about a file that cannot change unless the file does.
- [x] `whisper-large-v3` and `-turbo` on Groq (same key as its chat models) and
      `whisper-1` on OpenAI, in both copies of `providers.yaml`. The `kind`
      filter in `candidates_for` needed no change — it was already generic.
- [x] Verified against an independent implementation: WAV files written by
      Python's stdlib `wave` module parse to the exact sample rate, channel count
      and duration.
- Not built: karaoke highlighting (the word timings are stored, the renderer
  cannot colour part of a line), translation, speaker labels, browser recording.
  **Imported footage is audible but not drawable** — its sound captions fine, the
  picture is not painted, and the manifest says so and marks the project
  unrenderable rather than exporting a hole.

### Video editor — timeline core and browser render (2026-08-14)
- [x] `offsetx_apollo_builder/video/` + `frontend/src/video/` + the **Video
      editor** screen. Docs: `docs/architecture/VIDEO_EDITOR.md`; the feature
      inventory it was cut from is `docs/architecture/CAPCUT_FEATURE_MAP.md`.
- [x] **The server owns the document; the browser draws it.** Every edit is a
      named operation, validated server-side, returned as a new document. One
      round trip per edit, and one place that decides whether an edit is legal —
      the same place that checks the exported file.
- [x] **Time is an integer at 90kHz**, the MPEG timebase, because it is the
      smallest rate whose frames are whole numbers at 24/25/29.97/30/50/60. A
      split at frame 100 is the same integer however many times the project is
      saved and re-split. An unlisted frame rate is refused, not rounded.
- [x] **Clips on a track cannot overlap.** Made unrepresentable rather than
      handled: an overlap means the renderer picks one, and which one it picks
      can differ between the preview and the export — the worst bug class an
      editor has.
- [x] **Every edit copies before it changes anything**, through
      `to_dict`/`from_dict`. A refused edit cannot half-apply and does not
      consume a step of undo.
- [x] **A split is transparent.** Both halves carry a synthesised keyframe at
      the cut, so the resolved animation is identical either side of it. A test
      resolves every tick across a split and asserts the two lists are equal.
      Trimming the head moves keyframes with the material for the same reason.
- [x] **Two resolvers, one fixture.** The browser must resolve keyframes itself
      — a preview cannot make a request per frame — so `timeline.py` and
      `resolve.ts` implement one rule twice.
      `tests/fixtures/timeline_conformance.json` holds a deliberately awkward
      document and the frame Python resolves at fifteen *chosen* ticks (the tick
      before a cut, the cut, the tick after, one past the end). Both suites
      assert against it. It forced `roundHalfToEven` in TypeScript, because
      Python breaks rounding ties to even and JavaScript breaks them upward.
- [x] **WebCodecs, and deliberately no MediaRecorder fallback.** MediaRecorder
      records in real time, drops frames silently, and writes no Duration —
      which would make the export gate unable to do its job. A fallback whose
      output cannot be verified is a quieter failure, so an old browser is told
      what it needs instead.
- [x] **A WebM muxer written by hand** (`frontend/src/video/webm.ts`), the same
      call `imagery/gates.py` made about Pillow. It buys an exact Duration
      written from the timeline that produced it.
- [x] **MP4 and WebM headers parsed by hand** (`video/gates.py`). Handles the
      display matrix (a phone records sideways) and version-1 64-bit boxes — a
      test caught a twelve-byte offset error in the latter during the build.
- [x] Gates: decodes, not_empty, readable_header, has_video_track, aspect_ratio,
      duration_matches, not_duplicate — checked against the project the file
      claims to be a render of. A failing render is **stored anyway** with its
      report: a gate result nobody can check the file against is an assertion,
      not evidence.
- [x] **Undo is a pointer move over stored history**, so there is no "unsplit"
      reconstructing what a split destroyed, and it survives a reload. Editing
      after an undo drops the abandoned branch. Capped at 300 versions.
- [x] Verified outside this project, not only by unit tests: the committed
      `muxed_sample.webm` is written by the TypeScript muxer and parsed by the
      Python gates in CI; ffmpeg reads it as `matroska,webm 1080x1920 3.00s vp9`;
      a real headless Chromium export passes the gates; and frame 0 of that
      export decodes to a blue rectangle of exactly 432x768 at (324, 576) —
      precisely scale 0.4 of a 1080x1920 canvas, measured rather than eyeballed.
- [x] Owned by the **image** campaign, whose registry entry always named video
      as what it was missing. `missing` is narrowed rather than cleared.
- Not built, and said plainly in the docs: **no AI feature is wired** (captions,
  cutout, reframe, text-to-video — every M row in the feature map); nothing
  generates video or audio material yet; no transitions (a dissolve is an
  overlap, which the invariant forbids — it needs a real transition object);
  the export holds the whole file in memory.

### Trend to post (2026-08-10)
- [x] `distribution/pipeline.py` — the piece that joins the three campaign
      kinds. Everything it needed already existed; this is the wiring, and it is
      what "run this campaign" finally means end to end. Docs:
      `docs/architecture/TREND_TO_POST.md`.
- [x] **Where the automation stops is the whole design.** Two halves, and the
      boundary between them is a judgement that already existed. `plan` goes
      topic -> brief -> candidates and **stops at the review queue**; `draft`
      takes the pictures the owner kept, writes captions and creates **draft**
      posts, which still need the approval the distribution runner has always
      required. The machine fetches, composes, generates and does the scheduling
      arithmetic; a person decides *is this picture good* and *does this go
      out*. Removing either would let the system publish something nobody saw,
      under the owner's name.
- [x] Both campaign ids are kind-checked in one call — the first must be
      distribution, the second image. A swapped id would otherwise write image
      briefs against an email campaign.
- [x] **The same topic is not planned twice.** Recorded by a key built from
      sorted terms rather than the label, because the label is the first three
      and a topic can gain a term between sweeps without becoming a different
      subject. A week's cooldown, or the review queue fills with the same
      picture every sweep.
- [x] Composition is **deterministic by default**, with an optional writer. The
      brief describes the subject and not the composition — over-specifying
      produces the same picture from every generator, defeating both running
      several and the swipe that compares them.
- [x] **The data class is chosen by what is sent**: topic terms and competitor
      titles are `public`; adding the owner's angle makes it `campaign`. The
      module decides nothing about trust — it labels honestly and the broker
      applies the rules it already has.
- [x] A failing or empty writer **falls back to the deterministic version**
      rather than costing the sweep. Tested both ways.
- [x] 21 new tests, all passing first run. Verified over HTTP, including the
      kind gate refusing a swapped campaign id.

#### Still not built
- Nothing calls it on a timer; that belongs in `AutomationService`.
- No UI for the plan/draft calls (the swipe half has one).
- One picture to three accounts carries the same caption to all three.
- The angle is a string the owner supplies — nothing derives it from their
  positioning or from what performed before, though `generator_performance` and
  the context layer both hold material that could.

### Topic clustering across channels (2026-08-10)
- [x] `distribution/topics.py`, surfaced at `GET /trends/topics` and inside the
      trends report. One channel running hot is a good week; several on one
      subject is an event, and the stronger signal.
- [x] **Distinct channels, not videos.** A channel posting five times about its
      own product has a content calendar, not a trend, so a term one channel
      uses scores one however often it repeats.
- [x] **A topic is a term common now and not before** — the same shape as the
      outlier multiple, one level down: share of channels inside the window
      against share outside, needing 2x lift. A term with no history at all is
      the strongest case, not a division by zero.
- [x] **Adaptive stopwords fall out of that for free.** Watch twenty logistics
      channels and "logistics" has a high baseline by definition, so the same
      arithmetic that finds a spike removes it. No per-industry list to
      maintain, and a hand-written one would still miss the words that matter to
      one owner and not another.
- [x] **Merging is on shared videos, not shared terms.** Term chaining is how
      clustering turns everything into one blob — A shares a word with B, B with
      C, and three unrelated stories become one topic. Tested with two
      simultaneous unrelated stories that must stay apart.
- [x] **Lexical, not semantic, and there is a test that says so.** "Rotterdam
      port strike" and "Dutch dockworkers walk out" share no word and will not
      group. Deliberate: semantic grouping means an embedding or a model call
      per sweep — a cost, a provider dependency, and a feature that dies with a
      key. The limitation is pinned by a named test so it is found here rather
      than by someone trusting the output.
- [x] 14 new tests, all passing first run.

### Trend detection on YouTube (2026-08-10)
- [x] `distribution/youtube.py` + `distribution/trends.py`. Docs:
      `docs/architecture/TREND_DETECTION.md`.
- [x] **YouTube because it is the only one of the four whose terms allow reading
      public data at scale** — no research application, no scraping. Instagram's
      Business Discovery is thin, TikTok's Research API needs approval, Facebook
      offers competitors almost nothing.
- [x] **The quota decides the design.** 10,000 units/day, and
      `search.list` costs **100** while a channel's uploads playlist costs **1
      for 50 videos**. A 1,000-channel sweep via playlists is ~1,100 units —
      daily. The same coverage via search is impossible: the whole budget buys
      100 searches. So `search` **exists only to refuse**, with the arithmetic
      in the message, and statistics are fetched batched 50 at a time.
- [x] Quota counted locally from documented per-call costs (Google exposes no
      live balance). A sweep that would exceed it **stops cleanly with a note**
      rather than raising halfway and leaving the day's picture half-updated.
- [x] **Raw view count is the wrong signal** — it returns the biggest channels'
      oldest videos every week, both already known. Two measures instead:
      velocity (views/hour, correcting for age) and **outlier multiple** (times
      the channel's *own* median). The multiple is the one that finds a subject
      rather than a channel, and there is a test where a small channel's
      20,000-view video outranks a big one's 520,000-view video because the
      first is 20x its baseline and the second is 1.04x.
- [x] A channel needs **5 observations** before its multiples are ranked; below
      that the video is listed and flagged rather than hidden, because hiding it
      would make the list depend on how long each channel had been watched. A
      20x multiple from two videos looks like insight and is arithmetic on noise.
- [x] Read-only, so **not** through the broker — same reasoning as
      `ai/discovery.py`: no owner data, only a channel id and a region code.
      Still written to the egress log so the record stays complete, and a test
      asserts the API key never appears in what is logged.
- [x] One module in `distribution/` has a transport and it is this one. The
      publishing path has none, and browser automation is refused across the
      whole package with no exception. The old blanket test was replaced by two
      precise ones rather than deleted.
- [x] 20 new tests, all passing first run. `/trends` works without a key from
      already-collected data; watching without one says so plainly.

#### Found while wiring it
- [x] `api/app.py` used `os.getenv` without importing `os`. It imported fine —
      the failure would have been a runtime `NameError` the first time anyone
      opened the trends screen.

#### Still not built
- Turning a trend into a post: `/trends` reports, nothing composes a caption
  from it. That is where this and the image campaign meet.
- Scheduled sweeps (nothing calls `/trends/sweep` on a timer).
- Topic clustering across channels — "six competitors posted about the same
  thing today" is a stronger signal than any one of them, and is not computed.

### Content distribution runner (2026-08-10)
- [x] `distribution/` — the third campaign kind, and the one that composes the
      others. All three kinds now have runners. Docs:
      `docs/architecture/DISTRIBUTION_CAMPAIGNS.md`.
- [x] **The hard part here is not code.** Each platform allows far less
      automated posting than it appears to, and the tools that seem to offer
      more are what get accounts banned. off_CRM publishes through **official
      APIs only**, and `platforms.py` declares every platform with its API, its
      preconditions, its quotas and what off_CRM refuses. Connecting an account
      it cannot post to is refused **at connection**, not at send time.
- [x] **One working adapter today: the local outbox** — not a stub, the same
      device `LocalOutboxProvider` is for email. The whole pipeline runs and is
      reviewable without touching a real account.
- [x] Quota facts recorded rather than assumed. YouTube's is **per API project,
      not per channel** (~6 uploads/day across every channel you own);
      Instagram's 25/day genuinely is per account. A planner assuming both were
      per-account would over-promise on YouTube by however many channels exist.
      Instagram's ceiling is checked **when a post is scheduled**, because a
      schedule that cannot be delivered looks like a plan.
- [x] Instagram's personal-account impossibility is refused by name; TikTok's
      unaudited private-only posting is refused rather than counted as reach.
- [x] **Goal-shaped**: "a million views", with progress against it.
- [x] **This closes the benchmark.** Gates and swipe were layers one and two
      from the image runner; engagement is layer three, and
      `generator_performance` joins it back — views grouped by the generator
      that drew the picture, so the owner's taste and the audience's can be
      compared and can disagree.
- [x] 20 new tests, and the whole loop verified over HTTP: campaign, account,
      goal, post, approve, schedule, publish, measure, progress (250,000 of
      1,000,000 views, 25%).

#### A real bug the tests caught
- [x] **Engagement snapshots were being summed.** `latest_metrics` picked rows
      by `MAX(measured_at)`, but timestamps were second-precision, so two
      readings a moment apart *both* matched the maximum and were added —
      reporting 100 views where there were 60, and a goal met when it was not.
      Now ordered by time then id, with microsecond precision on measurements.
      The test that caught it was written before the bug was known to exist.

#### Not built, recorded on the spec
- Adapters for the real platforms — each declared with the route that would
  serve it; each needs OAuth per account and, for Meta and TikTok, app review.
- Competitor watching and trend detection: the `read` column is the groundwork,
  the collector is not written, and it must be built on what terms permit.
- Automatic caption generation, scheduled publishing on a timer, and a UI.

### Image campaign runner (2026-08-10)
- [x] `imagery/` — the second campaign kind, and the first that produces
      something other than a message. `image` is now `implemented=True` with a
      runner. Docs: `docs/architecture/IMAGE_CAMPAIGNS.md`.
- [x] **The swipe is the label**, which is the answer to the owner's benchmark
      question. Not a model rating its own output — the owner's own decisions,
      collected free as a side effect of use. Every decision scores the
      generator that made the picture, and `ai/bandit.py` allocates the next
      batch on those scores using the same Thompson sampler that shifts traffic
      between email templates. The allocator does not know its arms are image
      models.
- [x] Three consequences, each tested: **a decision is made once** (or a score
      moves by clicking twice); **refresh counts as a rejection** (dropping the
      no would bias scores towards whatever got refreshed most); **rejection
      deletes the bytes and keeps the verdict** (the record of rejecting is what
      the benchmark is made of).
- [x] **It waits before steering.** Under 12 decisions per generator the
      allocator stays out of the way — a lopsided result from four swipes is
      noise, and acting on it would starve a generator that never had a fair run.
- [x] **Gates are layer one and are not about taste**: decodes, not_blank,
      readable_header, aspect_ratio (5% tolerance so a generator rounding to
      1152x648 still satisfies 16:9), not_duplicate. A gate failure is a
      separate status from a rejection — mixing "this came back broken" with
      "I do not like it" would poison the only real signal this kind has.
- [x] Failed candidates are **stored, not dropped**: "this generator returns the
      wrong ratio four times in five" is worth knowing, and a discarded
      candidate cannot say it.
- [x] **No image library.** Reading a width and a height is a header parse —
      PNG IHDR, JPEG start-of-frame walk, GIF, three WebP variants — so Pillow
      was not added to decode two integers. Fails closed on an unknown format,
      because a zero would silently pass a dimension check.
- [x] **Everything protective is inherited.** Generation goes through
      `EgressBroker.call_image`: same tier filter, same allowlist payload, same
      blocking scanner, same egress log. A structural test asserts `imagery/`
      imports no transport.
- [x] The kind gate now runs from **both sides** — `OutreachEngine` refuses an
      image campaign and `ImageCampaignEngine` refuses an email one.
- [x] Own database (`imagery.db`), three tables, and **pictures are files** at
      `0600` with the row holding a path and a hash. Same decision the egress log
      made when it chose to record the prompt and never the picture.
- [x] Seven API endpoints, and an **Image review** screen: one candidate at a
      time, three buttons, arrow-key shortcuts. One at a time rather than a grid
      because a grid invites picking a favourite and ignoring the rest, and
      "ignored" is not a label.
- [x] 22 new tests. Verified over HTTP end to end: an image campaign can now be
      created, the email runner refuses it by name, and generation with no image
      model connected fails with "Open Connectors and add one".

#### Still missing on this kind (recorded on the spec, not hidden)
- Video — the gates read image headers; duration, frame rate and audio are a
  different piece of work, and claiming video without them would claim a
  benchmark that does not exist.
- Publishing — an approved picture is an asset; posting it is the distribution
  campaign, which has its own credentials and per-platform rules.
- Layer three of the benchmark (views, watch time) needs distribution to exist.
- Brief authoring in the UI, and prompt improvement between rounds.

### Error classification (2026-08-10)
- [x] `ai/failures.py` + wiring in `ai/broker.py`. Docs:
      `docs/architecture/FAILURES.md`. The item deferred pending reading; the
      reading was of the codebase, and it changed the design twice.
- [x] **What it did before:** every provider failure treated identically —
      record, fail over, cool the model off after two. Right for a provider
      having a bad day, wrong for most of the rest.
- [x] **Three failures that cost money.** A rejected key failed over silently to
      a model that worked, so nobody found out while every call ran on a model
      the owner had not chosen. A payload *we* built wrong was tried against
      every provider in the tier and opened the circuit breaker on each. A 429
      fell through to a second provider's quota instead of waiting.
- [x] Four actions, and the classes exist only to choose between them:
      `RETRY_SAME`, `FAILOVER`, `STOP_REQUEST`, `STOP_CONFIG`. Both stops refuse
      to fail over, which is the point of them.
- [x] **Only provider-health failures open the circuit breaker.** A 400 says
      nothing about their service; letting it trip the breaker is how one
      malformed payload takes a whole tier offline.
- [x] **`unknown` fails over once and never retries** — default-deny applied to
      spending, and it lands in the log so the gap shows up there not in a bill.
- [x] **Reading the code changed the plan.** `outreach/providers.py` already
      retries three times for connection errors, 429 and 5xx, so no second retry
      loop was added: nine attempts at one model is a stuck request, not
      resilience. `RETRY_SAME` covers only what the transport does not, bounded
      by 2 retries and a **120s wall clock over the whole chain** — attempts,
      retries and failover share one deadline, and exceeding it is reported as
      `deadline_exceeded` rather than hidden.
- [x] `Retry-After` honoured when sent, capped at 300s.
- [x] `ProviderFailure` -> **502** carrying the kind, action and owner action.
      502 not 503: the upstream answered definitely and off_CRM chose not to
      route around it, so "try again later" would be the wrong advice.
- [x] `failure_kind` recorded in the egress log and grouped by
      `GET /ai/egress-log/stats`. This is the payoff: "NVIDIA has been returning
      auth errors for a week" is answerable with a kind column and not with a
      pile of 500-character strings.
- [x] **The log's first migration**, additive on both backends via the new
      `Database.add_column_if_missing` — which also closes one of the gaps the
      Postgres doc listed. Verified against a log built without the column:
      rows survive, the column appears.
- [x] `GET /ai/failure-kinds` serves the taxonomy so the inspector need not
      hard-code it.
- [x] 34 new tests.

#### Bugs found while building it
- [x] **`refus` matched "Connection refused".** The first content-filter pattern
      filed a dead network as a content filter, so off_CRM would have failed
      over politely instead of reporting nothing could be reached. Patterns on
      an error path are exercised by text nobody chose. A test pins the pair.
- [x] **A stray backspace character was written into that regex** by a patch
      script whose replacement string was not raw, so the word-boundary escape
      became a literal control character and the alternative could never match.
      Found by tracing which pattern fired, not by reading the file — the
      character is invisible. The package and test tree were scanned; it was the
      only occurrence.
- [x] `quota.record(rate_limited=...)` was a substring search for `"429"` over
      the message, which also fired on a body that merely contained those
      digits. Now driven by the classification.
- [x] A test of mine asserted failover between `mistral` (tier A) and `nvidia`
      (tier B) and got one candidate. That was the **failover-never-crosses-a-
      tier rule working**; the test was wrong and now uses two US providers.

### Response cache wired (2026-08-10)
- [x] The gap the rebuild-guide audit found is closed: `ResponseCache` is now
      constructed in `api/app.py` and passed to `EgressBroker`. Before this it
      was implemented, tested and exported with **no caller**, so no request had
      ever reached it.
- [x] **Switching it on surfaced a real defect first.** At `pseudonymous`
      policy a payload carries no name — everyone is `PERSON_1` — so two
      different prospects with the same title, category and an equivalent public
      hook build a **byte-identical** payload. Measured: two logistics directors
      who both "opened a new depot" score **1.000**, an exact hit. Wiring the
      cache as it stood would have sent both of them the same email body, which
      is the opposite of the product and exactly what spam filters cluster on.
      The 0.92 near-match threshold is no defence, because this is not a near
      match.
- [x] Fixed with an allowlist rather than a patch: **cache work whose output is
      a fact, never work whose output is a message.** `CACHEABLE_TASK_TYPES`
      holds `classify_reply`, `summarise`, `extract`, `enrich`,
      `orchestrator_plan`, `ai_chat`. An unlisted task type is not cached —
      default-deny, as everywhere else.
- [x] `NEVER_CACHE_TASK_TYPES` names `draft_email`, `template_rewrite` and
      `image_generation` **with the reason for each**, so the refusals are
      documented rather than merely absent. A test asserts every one carries a
      reason; refusals without reasons get "fixed" by the next reader.
- [x] Both axes checked independently: a never-cache data class wins even for an
      allowlisted task type.
- [x] **Evals never use the cache**, now explicitly `cache=None` with the reason
      in the source. An eval exists to measure a model; a cached answer makes it
      measure the cache, and those numbers feed a promotion decision. A test
      asserts the source still says so — the risk is someone "fixing" the
      missing cache later as an oversight.
- [x] `GET /ai/cache/stats` reports the hit rate **with** the allowlist and the
      named refusals; `POST /ai/cache/clear` empties a workspace. The published
      60–90% figures come from chat systems and do not apply to personalised
      outreach, so the only honest answer is a measured one.
- [x] Verified live: the app boots, `ai_cache.db` is created, and the stats
      endpoint serves the allowlist.
- [x] 14 new tests (48 in `test_ai_cache.py`). The existing suite had been
      written against "cache everything" and used `draft_email` throughout; it
      now uses a cacheable task type, and drafting has its own test that asserts
      the two-prospect payload collision and that nothing is stored or served.

### Rebuild guide, §10 (2026-08-10)
- [x] `docs/architecture/REBUILD_GUIDE.md`. Written **after** the system,
      describing what exists rather than specifying what should. Says so at the
      top: where the code and the guide disagree, the guide has the bug.
- [x] The abandoned `agent/off-crm-v0-12-ai-studio` branch had a 1,015-line
      rebuild guide. It was **not** reused: it describes `off_ai/`, a parallel
      module that was never merged. A rebuild guide for a system that is not
      there is the worst version of this document.
- [x] The content that lives nowhere else: **stage order with the reason each
      stage must come before the next**. Three orderings carry the security
      properties — scanner before any provider adapter (or the direct call site
      you made to test it survives as a second door); construction before
      everything (filtering is a one-way door); eval harness before the verify
      loop (or the loop invents weaker checks and measurement quietly disagrees
      with enforcement).
- [x] **15 traps**, each a real mistake, most of them made and fixed here. They
      share a shape: every one looks like a simplification and silently removes
      a guarantee.
- [x] The architecture rules that are enforced by AST tests rather than by
      discipline, listed with what enforces each. Includes the doubled-test
      pattern from campaign kinds: a list that must stay exhaustive needs a
      second test that checks the list itself.

#### Facts corrected while writing it
Every number in the guide was measured rather than recalled, and four claims
written from memory were wrong:
- [x] `ai/` is 24 modules / 10,303 lines; the package root has 24 more, not 15.
- [x] The single-gate test does not assert "three call sites". It parses every
      file in the package and fails if any module outside a **three-file
      allowlist** imports a provider constructor. Different rule, stronger.
- [x] Six named SQLite databases, not seven — and only four are opened by the
      web app; `ai_evals.db` and `ai_tools.db` belong to their CLIs.
- [x] **The response cache is not wired into anything.** `ResponseCache` is
      implemented, tested (34 cases) and exported, and `EgressBroker` accepts
      one as an optional argument — but no caller constructs one, so no request
      has ever hit it. Recorded in the guide so a rebuilder does not hunt for
      wiring that does not exist. Left unwired rather than switched on in the
      same change as a documentation task.

#### Fixed while writing it
- [x] `db/copy.py` imported `ai/log.py` for its schema — the generic backend
      layer knowing about one specific store, and the reverse of the dependency
      rule the guide states. Writing the rule down is what exposed it. `db/`
      now has a table-agnostic `copy_table(table, columns, schema, key)`, and
      the egress-log wrapper lives in `ai/log.py` where its schema is defined.

### Postgres backend, egress log first (2026-08-10)
- [x] `offsetx_apollo_builder/db/` — ~250 lines. `open_database()` returns
      something that behaves like the `sqlite3.Connection` the stores already
      use: same `execute` / `executescript` / `transaction`, same `row["col"]`
      and `dict(row)`. Docs: `docs/architecture/POSTGRES.md`.
- [x] **No ORM.** SQLAlchemy would have replaced auditable SQL with expression
      trees in a codebase whose security argument depends on reading the
      queries, for a much larger diff and the same result.
- [x] `?` → `%s` translation in `db/translate.py`, as a **character walker, not
      a regex**: both `?` and `%` occur inside string literals, and a blind
      replace corrupts data invisibly until someone reads the row back. Handles
      `'it''s'` (a doubled quote is an escape, not the end of the string) and
      doubles literal `%`, which psycopg treats as a placeholder marker.
      `outreach/store.py` alone has 449 `?`, so rewriting them was never the
      option.
- [x] Postgres runs in **autocommit** to match SQLite's `isolation_level=None`.
      The stores expect a statement to be durable when it returns; psycopg's
      default open transaction block would have changed that contract silently.
- [x] **The egress log is the store that moved, because it is the one broken in
      the deployed environment today.** §6.4: on Render `OFFSETX_DATA_DIR` is
      `/tmp`, wiped every restart. Everything else there is an inconvenience to
      lose; the audit trail is a hole in the argument — a verification trail
      that resets verifies nothing. It also has no foreign keys into the CRM.
- [x] **A bug the second engine found.** `EgressLog.stats()` selected
      `provider_name` and `jurisdiction` while grouping only by `provider_id`.
      SQLite runs that and picks an arbitrary row; Postgres refuses it. Now
      grouped on all three, which is also the answer that was meant.
- [x] `offsetx-db check` and `offsetx-db copy-log`. The copy never deletes the
      source, is idempotent by primary key, counts both sides and reports, uses
      an explicit column list (a test fails if it drifts from the schema), and
      masks passwords in everything it prints.
- [x] Only an explicit `postgresql://` / `postgres://` / `psql://` scheme means
      Postgres; everything else is a path, so a mistyped DSN fails loudly rather
      than silently creating an empty SQLite file that looks like it worked.
- [x] Resolution order is explicit → `OFFSETX_DATABASE_URL` → default path. The
      middle rung lets a deployment set one variable; the top rung keeps a
      test's scratch file safe from the environment reaching in.
- [x] Missing psycopg raises a sentence containing the install command, not
      `No module named 'psycopg'`.
- [x] Log tests are **parametrised over both backends**, 35 of them. The
      Postgres half skips with a reason unless `OFF_CRM_TEST_POSTGRES_URL` is
      set — same rule as the live Docker test.
- [x] Verified end to end against a real Postgres 16: the app boots with the log
      on the server, `GET /ai/egress-log/stats` reports `"backend": "postgres"`,
      no `ai_egress.db` appears in the data directory, and the CRM keeps working
      on SQLite in the same process.

### Campaign kinds (2026-08-10)
- [x] `campaigns` gained `kind TEXT NOT NULL DEFAULT 'email'`, schema v8.
      Registry in `offsetx_apollo_builder/campaigns.py` — **package root, not
      inside `outreach/`**, because the registry is above the email runner
      rather than part of it. Docs: `docs/architecture/CAMPAIGN_KINDS.md`.
- [x] **The migration was the easy half.** Every pre-existing row was an email
      campaign because nothing else existed, so the column default backfills
      them and there is no data migration to get wrong. The hard half is the
      code written when email was the only possibility.
- [x] **The gate.** `OutreachEngine._require_own_kind` refuses a campaign of
      another kind at all nine entry points that act on one: `import_contacts`,
      `generate_drafts`, `edit_draft`, `bulk_replace_drafts`, `schedule_drafts`,
      `approve_drafts`, `sync_replies`, `run_due`, `export_crm`. Without it the
      first image campaign would be handed to the mail sender.
- [x] Two tests keep that list honest: one asserts each listed method contains
      the check, and one walks every public method taking a `campaign_id` and
      fails if any is missing from the list. Without the second, the first
      quietly stops being exhaustive the day someone adds a method.
- [x] `run_due` is checked **before** it syncs replies, with a test whose mail
      provider raises if touched — a refusal after the mailbox has been read has
      already done the thing it was meant to prevent.
- [x] Three kinds declared, one implemented. `image` and `distribution` refuse
      at creation with **what is missing**, rather than being omitted. The
      failure mode of a bare `kind` column is a database of campaigns nothing
      will ever run; a refusal at creation is the alternative to discovering
      that a week later.
- [x] **Absent means email, wrong means stop.** A missing value is a row written
      before the column; a present unrecognised value raises. Falling back to
      email there would hand an unknown campaign to the mail sender.
- [x] `kind` is fixed at creation — `update_campaign` refuses a change rather
      than dropping it through the allowlist, because the campaign's contacts,
      drafts and messages were all made under the original kind.
- [x] The index over the new column is applied **after** the migration
      (`POST_MIGRATION_SQL`): on an existing database `CREATE TABLE IF NOT
      EXISTS` is a no-op, so an index over a brand-new column in `SCHEMA_SQL`
      would be asked for before `ALTER TABLE` added it and every upgrade would
      fail on startup.
- [x] Surfaced end to end: `GET /api/v1/campaign-kinds`, `kind` on create and as
      a list filter, `offsetx-outreach campaign-kinds`, and a picker in the
      Campaigns screen that shows unbuilt kinds greyed with their reason and
      hides the email-shaped fields when one is selected.
- [x] **Settings blob deliberately not built.** Email's settings are real
      validated columns and no other kind can be created, so `settings_json`
      today would be an unvalidated blob with no writer. The column is additive
      and costs the same later; the validator is what has to come first.

### Code graph (§4K, 2026-08-10)
- [x] `codegraph.py` + `offsetx-codegraph` (`policy`, `build`, `status`,
      `verify`, `ignore`). Docs: `docs/architecture/CODE_GRAPH.md`.
- [x] Wraps Graphify (`graphifyy==0.9.39`, pinned, run via `uvx` so it never
      enters the project venv). 7 seconds for this repo: 3,047 nodes, 7,935
      edges.
- [x] **The reason it is a module and not a shell command:** `graphify extract`
      is, in its own help, "AST + **semantic LLM**" — it finds an API key and
      posts chunks of source to gemini/openai/deepseek/claude/kimi/ollama.
      `--code-only` makes it "local AST, no API key". Two flags separate a build
      step from an egress event. The previous attempt put them in
      `scripts/build_code_graph.ps1`: PowerShell only, and editable.
- [x] `--code-only` is not a parameter of `extract_command()`. A keyword
      argument would put the unsafe call one keystroke away.
- [x] Seven refusals, each with its reason: the semantic path, `label`,
      `add <url>`, `--global` (merges into a shared file in `$HOME`), the
      `install` subcommands (they write to AGENTS.md and install git hooks),
      `--no-gitignore`, `--postgres`.
- [x] **Verified, not asserted.** After every build the graph is read back and
      **deleted** if any indexed file lives under a runtime-data path. Kept-with-
      a-warning is not an option: someone queries it anyway because the file is
      there.
- [x] `.graphifyignore` is generated from `RUNTIME_DATA_PATHS` in code,
      overwriting hand edits, and a test cross-references that list against
      `api/config.py` so the two cannot drift.
- [x] **Live probe run, three ways** (recorded in the doc): a planted
      `local_data/leak_probe.py` is excluded by `.gitignore` alone (0 nodes) and
      by `.graphifyignore` alone (0 nodes); with **both** bypassed it leaks 2
      nodes and the verifier rejects the graph by name. Each layer holds
      independently and the backstop fires when both are cut.
- [x] Staleness: `graph.json` records `built_at_commit`; `status` compares it to
      HEAD. A graph recording no commit is treated as stale.
- [x] `graphify-out/` gitignored — build artefact plus a 4.6 MB cache, rebuilt
      in seconds.

### Fixed defects found during the audit
- [x] **AI chat leaked.** It passed the raw conversation to a provider with no
      policy applied, while its own docstring claimed the opposite. Chat now
      goes through the broker. `ai_chat.py` no longer imports any transport, and
      a test asserts it never will again.
- [x] **Scanner newline bug.** Patterns ran against a JSON dump, which escapes
      `\n` and silently disabled every `^`-anchored mail-header rule — the
      payload looked clean exactly when it held a pasted email. Patterns now run
      against raw string values.
- [x] Removed `frontend/src/providerCatalog.ts`, which hardcoded providers in
      TypeScript and recommended DeepSeek for "bulk email generation".

---

### Public discovery frontier — S-05.01.01 (2026-09-18, IN_REVIEW)

- [x] The old per-run `deque` is gone from the production discovery path.
- [x] `crawler_frontier.sqlite3` persists URL, depth, content hash, last
      crawl/change, next due time, counters, last error and a short claim lease.
- [x] Changed pages are due after one day; unchanged pages back off by observed
      stability up to 30 days; failures back off separately up to one day.
- [x] Claims are transactional and leased, so two processes sharing the file do
      not intentionally take the same due URL. A dead worker's lease expires.
- [x] Every seed/link still goes through the existing public URL policy before
      persistence. Session-gated social domains lose even if mistakenly present
      in an allow-list.
- [x] Existing SafePublicFetcher/Crawl4AI robots, crawl-delay, SSRF, redirect and
      size controls are reused rather than copied.
- [x] Seven focused tests cover robots + crawl delay, adaptive revisit cadence,
      restart/budget persistence, concurrent claim exclusion, stale-policy
      revalidation without queue starvation, the social boundary and shared
      cross-process host pacing.
- [x] CHECK-mode cold review on 2026-09-23 found and fixed D-71:
      a persisted URL rejected by the current policy could repeatedly consume
      the claim limit and starve valid due work behind it. The regression test
      is committed; no public interface or schema changed.
- [ ] Locked repository test evidence is still missing. GitHub Actions runs 584
      and 590 failed before creating a workflow step and expose no job log.
      Under the Definition of Done this is IN_REVIEW, not DONE.


### CI evidence infrastructure — S-06.02.18 (2026-09-23, BLOCKED)

- [x] Workflow source reviewed: the `quality` job targets standard
      `ubuntu-latest`; step 1 is `actions/checkout@v4`.
- [x] Current head re-run attempted. Run 1205 / 35779093017, attempt 2,
      created job 106939339831 and failed before runner allocation.
- [x] Jobs API evidence: `steps = null`, `logs_url = null`; no repository
      command executed.
- [x] Application/test changes are not a valid fix for a failure that occurs
      before step 1.
- [ ] Owner-side Actions billing/budget/payment and repository Actions policy
      must be checked. If clean, GitHub Support must investigate hosted-runner
      provisioning.
- [ ] After runner capacity is restored, execute the locked closure chain:
      S-05.01.01 → S-05.01.02 → S-05.01.03.

### Reports and artifacts — S-07.01.04 (2026-09-18, IN_REVIEW)

- [x] Existing verified trace findings are the only content source. Artifact
      generation has no broker/provider/model route.
- [x] XLSX uses the installed openpyxl dependency, includes Findings + Trace
      sheets and internally hyperlinks every claim to its exact trace-step row.
- [x] Spreadsheet formula prefixes from hostile page text are forced to literal
      strings; invalid XML control characters are normalised before writing.
- [x] PPTX is a small standard-library OOXML package: title slide plus one slide
      per finding, with value, quote, source URL, capture time and trace step.
      No macros or external relationships.
- [x] PDF reuses the already-hardened offline HTML report and prints it through
      installed Chromium with a temporary empty profile and background networking
      disabled. No second PDF renderer or dependency.
- [x] Broken provenance fails closed before an artifact is written.
- [x] `offsetx-artifacts` exposes XLSX, PPTX, PDF and all locally.
- [x] Ten focused tests cover format structure, trace linkage, hostile text,
      output privacy, PDF browser contract, CLI behaviour and the no-AI rule.
- [ ] Locked executable evidence is pending. GitHub Actions is still creating
      failed quality jobs with zero workflow steps, so this story cannot be
      called DONE until the test command and board verifier actually run.
- [x] D-102 (D-51 on its branch) was caught before review: a scripted metadata edit wrote a literal
      `\\n` into `pyproject.toml`; the committed file was re-read and fixed.
- [x] Supplemental format probe: the exact PPTX package shape opened in
      LibreOffice Impress and converted to PDF successfully.
- [ ] Live PDF rendering is not certified in this container. Root Chromium
      correctly refuses to run with its sandbox; a non-root probe did not
      complete here. No `--no-sandbox` weakening was added to make the probe
      pass.

## 4. Not built yet

Listed honestly. Nothing below is silently assumed done.

| § | Item | Note |
|---|---|---|
| 4D | Two-mode campaign intake | **Built** (`intake.py`). Generate/Parse split, plus PDF reading. Deliberately outside `ai/` — a contact list must never reach a model. Remaining: no UI screen, and generate mode is the brief object only; wiring it to discovery is separate. |
| 4G | NotebookLM export | **Built** (`notebook.py`, `offsetx-notebook`). Remaining: no API endpoint and no UI screen — and the web shape has a real problem to solve first, since a zip download would put the identity key back inside the folder the owner uploads. Two separate downloads is probably the answer and needs deciding, not defaulting. No scheduled re-export. |
| 4H | Bandit / automatic traffic shifting | **Built** (`ai/bandit.py`, `context.traffic_split`). Decides *how much* traffic each approved variant gets; still never decides *whether* a rewrite goes live — that stays with the owner per §3. |
| 4J | Bring-your-own tools, sandboxed | **Built.** Isolation in `ai/sandbox.py`, registry in `ai/tools.py`, CLI `offsetx-tools`. §5.12(c) covered. Remaining: no model-facing path yet (nothing hands the catalogue to a model or lets a plan call a tool — deliberate), no UI screen, and the container flags still need one live run against a real daemon. |
| 4K | Graphify code graph | **Built** (`codegraph.py`, `offsetx-codegraph`). Remaining: no CI job, no automatic rebuild on commit (Graphify's git hooks are on the refused list), and nothing inside off_CRM reads the graph — handing a model a map of the codebase is a separate decision. |
| — | Campaign `kind` column | **Built** (`campaigns.py`, schema v8). Remaining: no `settings_json` blob — deliberately deferred until there is a kind whose settings are known, since a validator has to exist before the blob does. |
| — | Postgres | **Partly done.** The seam is built and tested (`db/`). On either backend now: the egress log, video, GTM, keys, settings and logins (`S-06.03.02`), and the **CRM with its sales tables** (`S-06.03.03`). Still SQLite-only: context, recall, scoreboard, cache — `S-06.03.06` decides each. Migrations: a schema version per store in `offcrm_schema` (`db/schema.py`), the CRM's under `crm`. Still missing: FTS (`fts5` → `tsvector` is a reimplementation; expert search is unranked on PostgreSQL) and connection pooling. |
| E-12 | GTM engine, the rest | Phase 1 and 2 are built (section 3). Remaining, each with a backlog id: the video director reading the product (`S-12.01.03`), the expert corpus (`S-12.02.05`), posting from the screens (`S-12.02.06`), video in the email (`F-12.03`), driving external GTM tools (`F-12.04`), audience → Apollo search (`F-12.05`). |
| 10 | Rebuild guide | **Written** — `docs/architecture/REBUILD_GUIDE.md`. Stage order with the reason each stage must precede the next, the 15 traps, the invariants that are enforced by AST tests, and what is deliberately absent. |

---

## 5. Decisions and why

1. **`full` policy kept as a user choice.** The brief said addresses never leave;
   the owner overrode that and asked to keep the freedom. Implemented as: full
   is available on any tier, but above a tier's ceiling it needs an override
   with a written reason, stored with who decided and when. Never silent, never
   a default, never reached by failover.
2. **Chinese providers stay enabled and useful — but pseudonymously.**
   *Superseded 2026-07-31.* The original decision gave tier C the person's real
   public name, company and title. The owner then identified client and POI
   identity as the business secret, which contradicts it. Resolved by adding a
   `pseudonymous` policy between `strict` and `minimal` and lowering tier C's
   ceiling to it: a restricted provider still receives the job title, category
   and public hook — enough to write something specific — but the person and
   company arrive as `PERSON_1` and `COMPANY_1`, and owner-typed free text is
   scrubbed of the name as well. off_CRM re-attaches the real values locally,
   the same way it already does for addresses. `minimal` is unchanged for tiers
   A and B. Tier C is still useful for public and coding work at full detail.
3. **Google demoted to C.** Acceptable jurisdiction, but free-tier terms permit
   training on input. If billing moves to paid, re-verify and pin `trust_tier: B`
   with a note.
4. **SQLite kept.** Swapping the 2,221-line store to Postgres mid-hardening
   would have risked 88 passing tests for no security gain. Flagged above.
5. **Per-workspace, not global.** Multi-user from the start: one colleague
   raising a provider cannot change what another's calls send.
6. **Log payloads on by default.** The older audit defaulted to off, which meant
   it could only report "42 characters were sent" — useless for the question the
   owner actually has. Bounded at 20k rows.

---

## 6. Open questions for the owner

1. **Recall coverage** — the index covers sent mail. Whether attachments and
   older archives outside off_CRM should be pulled in is an owner decision.
2. **Orchestrator** — confirm the §7 reversal, and which model is the head.
2b. **Tier C and person identity — resolved 2026-07-31.** Pseudonymised; see
   §5.2. Open sub-question: whether `PERSON_1` / `COMPANY_1` should become
   stable *across* jobs for the same contact, so a model could in principle
   recognise a returning prospect. Today they are constant per payload, which
   means no mapping table exists and there is nothing to leak. Making them
   durable would need a stored mapping and is a real trade — flagged, not built.
   *Partly answered 2026-08-10:* the notebook export needs distinct tokens
   within one bundle or the export says nothing, so it numbers `PERSON_1..n`
   **per bundle** and writes the mapping to a file outside the uploaded folder.
   That is a stored mapping, but a local one with a single obvious owner. If
   cross-job stability is ever wanted, that file is the shape it should take —
   not a column on `contacts`.
3. **Positioning line** — set per workspace in Connectors; no default shipped.
4. **Render deployment** — `render.yaml` deploys `branch: main` with
   `autoDeploy: true`, so nothing ships until this branch is merged there.
   Two things to set up before the first deploy:
   - *(Superseded 2026-09-25, `DD-64`: keys are typed in the app only. The
     environment fallback this line described handed the owner's key to every
     workspace login (`D-151`) and is gone; keys surviving a deploy is
     `F-06.03`.)*
   - **The egress log lives in the same disposable `/tmp` directory.** It is
     the audit trail, and on Render it resets on every restart. Fine for a
     demo; a real shared deployment needs a Render disk or Postgres.
5. **Postgres** — needed before "millions of users"; say when.

---

## 7. How to verify the wall yourself

```bash
python -m pytest tests/test_ai_egress_wall.py -v   # 30 security cases
python -m pytest tests/test_ai_api.py -v           # 15 API cases
```

Then in the app: **Connectors** → connect a provider → **What was sent** →
Inspect any row. The payload shown is byte-for-byte what left the machine.


---

### Workspace isolation — S-06.01.01 (2026-09-20, IN_REVIEW)

- [x] Replaced the single hard-coded `local` browser-login identity with a
      persistent workspace account store. Passwords are scrypt hashes; signed
      cookies bind username + workspace + expiry + session version.
- [x] Provider keys and browser session vaults remain encrypted and keyed by
      workspace. Password rotation/disable increments session version so old
      cookies stop working.
- [x] Workspace administration requires the install API token. Ordinary
      workspace sessions cannot create or alter another workspace.
- [x] Removed the shared mutable `ai_broker.credential_resolver`. Every request
      now gets a credential-bound broker view; shared quota/cache/log/circuit
      state remains shared without sharing credentials.
- [x] Backup/privacy coverage now includes workspace auth and encrypted workspace
      AI state.
- [x] Focused regression tests are committed in
      `tests/test_workspace_isolation.py`, including concurrent credential
      isolation.
- [ ] Executable locked test/full-regression/verifier evidence is not available
      on this branch head yet, so the story stays IN_REVIEW.

### Agent routines — S-06.01.04 (2026-09-20, IN_REVIEW)

- [x] Durable interval and event declarations persist in
      `agent_routines.db`; duplicate scheduler/event deliveries are claimed
      transactionally.
- [x] Creation checks `check_navigation(..., unattended=True)`, so an
      attended-only target is refused before it can be scheduled.
- [x] Routine browser use is serialized per workspace with a renewable
      cross-process lease and named Docker containers are explicitly removed.
- [x] A routine notification requires the existing AgentRun provenance system
      to return a verified `notification` finding. Plain model prose such as
      “No updates found” cannot create a notification.
- [x] Routine state participates in encrypted backup and subject-access/deletion.
- [x] Focused acceptance tests are committed in `tests/test_agent_routines.py`.
- [ ] Executable locked test/full-regression/verifier evidence is still missing;
      story stays IN_REVIEW.

### Prompt secret boundary — S-06.02.01 (2026-09-20, IN_REVIEW)

- [x] Audit found a real bypass: `system_prompt` was provider-visible but was
      outside `scan_payload`. Transcription filename/media type/language were
      also outside the scanned payload object.
- [x] Added `scan_model_input`, which scans the constructed payload plus every
      separately transmitted model/provider-visible text field.
- [x] Text, image and transcription broker paths all scan before provider
      instantiation/I/O. Transport API keys remain transport credentials and are
      never inserted into model-visible input.
- [x] Adversarial tests plant credential material in payload, system prompt,
      image prompt and transcription metadata and assert the provider is never
      instantiated.
- [ ] Executable locked test/full-regression/verifier evidence is still missing;
      story stays IN_REVIEW.


## 2026-10-13 continuation on develop

Next three areas requested by owner: reliable Git board verification (S-06.02.20), hosted PostgreSQL backups (S-06.03.04), and companion playbooks loaded on demand (S-04.01.02). S-06.02.20 implementation and Git-based tests are in IN_REVIEW after an isolated 3-case test pass; complete repository suite and CI jobs have not executed. S-06.03.04 and S-04.01.02 have scoped work orders and remain BACKLOG, blocked from READY by Q-29/Q-30 and upstream companion review respectively. S-06.02.23 audit stays the only IN_PROGRESS item. All pushes to develop only. See `docs/DEVELOP_NEXT_WORK.md` and `docs/evidence/S-06.02.20-validation.md`.

## 2026-10-13 latest owner-authorised three-story batch
Implemented and pushed on develop: S-06.02.37 skip-link click handler + two route regression cases; S-03.01.03 deny internal literal hosts and noncanonical aliases in browser policy + guard tests; S-05.01.04 Requests DNS-IP-pinned HTTP/HTTPS transport + regression cases. Each is IN_REVIEW; see `docs/evidence/S-06.02.37-validation.md`, `docs/evidence/S-03.01.03-validation.md`, `docs/evidence/S-05.01.04-validation.md`. Full repo tests, real Chromium, Docker firewall and Crawl4AI protections remain open. S-06.02.23 continues IN_PROGRESS. Main unaffected.

## 2026-10-13 owner-selected latest three stories

Active branch: `develop` only. Newly selected: `S-06.02.36` (explicit install-owner login confirmation), `S-06.02.28` (path-aware CLI restore leases with shared local dotenv defaults), `S-06.02.34` (local AI provider usage, classified reporting support, OpenRouter/DeepSeek on-demand balance). Code, tests and work orders were committed for all three. They are **IN_REVIEW, NOT DONE**: full Python/front-end tests, CI, real restore contention and live vendor endpoints were not executed in this environment. Provider response-header quota capture remains unimplemented and must not be described as available. See individual evidence files. The production-audit S-06.02.23 stays the only IN_PROGRESS story; main untouched.

## 2026-10-13 — Latest three-story build on develop

Selected and source-implemented in sequence: S-12.01.03 (video direction product/style classified and system prompt audited); S-06.02.16 (CI npm production+development vulnerability gates); S-12.02.05 (GTM expert and winning-template references with A/B reference ablation). S-02.02.03 was considered but not pulled because upstream S-02.02.02 is IN_REVIEW and the Definition of Ready requires a DONE dependency. All three selected stories are **IN_REVIEW, not DONE**. Evidence: `docs/evidence/S-12.01.03-validation.md`, `docs/evidence/S-06.02.16-validation.md`, `docs/evidence/S-12.02.05-validation.md`. Real npm audit, frontend/Python tests, live video/provider checks, owner GTM corpus and 30 judged cases remain outstanding. GitHub Actions runners continue to fail before any step. The only IN_PROGRESS story remains S-06.02.23. Only develop edited; main untouched.


## 2026-10-13 — Send Queue pagination, full-campaign counters, review cohorts

Owner authorised another three-feature continuation on develop. Code/test-source, work orders, board entries, decision log, changelog and defect log were updated for **S-06.02.47** (Queue API/UI paginated to 100 by default), **S-06.02.48** (campaign-wide Ready/Needs approval/Replied totals independent of page and future scheduled time) and **S-06.02.49** (read-only All/Approved and due/Needs approval/Replied views). Sender `OutreachStore.send_queue(campaign_id, now=...)` still iterates the whole campaign; the UI alone passes explicit page IDs, with its own lightweight full-control scan. Ready is a candidate count, **not** permission to send; all existing live-send gates remain.

Work orders: `docs/work-orders/S-06.02.47-queue-pagination.md`, `S-06.02.48-global-queue-totals.md` and `S-06.02.49-actionable-queue-views.md`. Evidence: `docs/evidence/2026-10-13-queue-next-three.md`. Python regressions: `tests/test_queue_views.py`, frontend `frontend/src/pages/Queue.test.tsx`. **No test execution, production/live browser/PostgreSQL exercise or DONE claim this session**: GitHub Actions `quality` and `postgres` continued to fail before a runner executed any steps. Need full suite, CI, browser, independent review and server restart acceptance. All three stories stay IN_REVIEW; `S-06.02.23` is still the sole IN_PROGRESS audit. Central defects D-271–D-279 have now been recorded in `DEFECT_LOG.md`, including this batch's D-277–D-279. Working branch: **develop** only; **main** was not promoted.

Rollback: revert UI queue paging/filtering and API view endpoint, revert `send_queue_view` and `send_queue(only_ids=...)` optional argument; existing sender remains unchanged. No migrations, external sends, credentials or hosted configuration changes.

## 2026-10-13 — Feature-level Campaign operations continuation

The owner asked explicitly for three *features*, not three story-sized changes. New features selected and source implemented on **develop**:
1. **F-06.04 Campaign Management** — real settings editor for email schedule, cap, timezone, followups, approval and experiment; name-only edits for nonemail kinds; explicit typed Archive and safe paused restore. `OutreachStore` now validates IANA timezone on both create and update.
2. **F-06.05 Campaign Blueprint Reuse** — new authenticated idempotent POST clone API; copy only validated config, not recipients, drafts, mail history or keys; new campaigns start paused *inside* transaction, not in a follow-up update. UI supports naming and selection.
3. **F-06.06 Campaign Performance Intelligence** — real per-campaign CRM reporting, unique contacted audience, outbound count, manual unsent replied exclusion, rate over unique-contacted only, terminal counts and persisted draft status; UI on-demand drill-down and refresh.

Primary code: `offsetx_apollo_builder/outreach/store.py`, `offsetx_apollo_builder/api/{schemas,app}.py`, `frontend/src/pages/{Campaigns,CampaignOperations}.tsx`, `frontend/src/types.ts`. Regression tests **authored, not executed**: `tests/test_campaign_product_features.py`, `frontend/src/pages/CampaignOperations.test.tsx`. Product specs: `docs/features/campaign-management.md`, `docs/features/campaign-blueprints.md`, `docs/features/campaign-performance.md`. Full evidence ledger: `docs/evidence/2026-10-13-campaign-three-features.md`.

No migration. Full pytest/Ruff/Vitest/build/board verifier, PostgreSQL/Chromium, restarted host and independent security review remain gates; GitHub Actions runners are still failing before executing steps. All three feature entries remain **IN_REVIEW**, not DONE/deployed. Production disk durability, email worker, SMTP/provider and workspace tenancy blockers unchanged. The prior audit S-06.02.23 remains sole IN_PROGRESS. Rollback code/UI while preserving real paused cloned campaigns (archive unwanted copies explicitly).


## 2026-10-14 — Audience, readiness and audit timeline features

Develop-only source continuation, selecting product features, **not isolated stories**: `F-06.07` Audience Management Workspace, `F-06.08` read-only Campaign Launch Readiness Center and `F-06.09` Campaign Activity/Audit Timeline. Code is `offsetx_apollo_builder/outreach/{store,launch}.py`, `offsetx_apollo_builder/api/{schemas,app}.py`, `frontend/src/{App.tsx,pages/Contacts.tsx,pages/AudienceOperations.tsx,pages/LaunchReadiness.tsx,pages/CampaignActivity.tsx}`. Tests authored `tests/test_audience_launch_activity.py` and `frontend/src/pages/AudienceLaunchActivity.test.tsx`. Feature contracts and rollback: `docs/features/audience-workspace.md`, `campaign-launch-readiness.md`, `campaign-activity-timeline.md` and `docs/evidence/2026-10-14-audience-readiness-activity.md`.

No automatic sending, approval, contact deletion, background worker, storage migration or paid provider used. Pending full Python/frontend/test commands, real Postgres/Chrome, concurrency and independent review; previous Actions jobs allocated **zero** steps. Never claim DONE or deployed from source alone. Board: three IN_REVIEW features, one existing S-06.02.23 IN_PROGRESS. The original sender and full-campaign queue remain unchanged, as do legacy event payload responses. Rollback UI/endpoints/helpers without deleting retained contact, stop and event records.


## 2026-10-14 — Reply Inbox, Contact History and Human Tasks

Mode TASK · Product-level continuation on `develop` only. Feature IDs F-06.10, F-06.11, F-06.12, all **IN_REVIEW**. Source:
- `offsetx_apollo_builder/outreach/relationships.py`: campaign-scoped latest-reply list and per-contact outcome review, read-only bounded conversation, task CRUD with revision CAS.
- `offsetx_apollo_builder/outreach/schema.py`: two tables (triage and tasks), CRM SQLite SCHEMA_VERSION 10; `outreach/store.py` PostgreSQL schema step 2; `api/{schemas,app}.py` protected APIs, strict inputs, create idempotency, stale update 409.
- `frontend/src/pages/{ReplyInbox,ContactConversation,Followups}.tsx`; registered navigation in `App.tsx`; history accessible from `Contacts.tsx`.

Requirements, UI and release gates: `docs/features/reply-inbox-triage.md`, `contact-communication-history.md`, `human-followup-tasks.md`, `docs/evidence/2026-10-14-relationships-batch.md`. Authored tests: `tests/test_relationship_workflows.py`, `frontend/src/pages/RelationshipWorkflows.test.tsx`; expected CRM inventory increased from 31 to 33 in `tests/test_crm_hosted.py`. Original send code not touched. No task reminder or autonomous follow-up sends. Contact review outcome is not the shared global contact label. Assignments are labels, not RBAC.

**Mandatory gates open:** no runnable repository checkout in this session; no pytest/Ruff/Vitest/build/Chromium or PostgreSQL migration evidence. Previous Actions `quality` and `postgres` failed before a step; inspect new run before any DONE assertion. Need tenant isolation Q-27 review, real hosted backup/key-custody plan, baseline and upgrade database restore, SQLite 9→10/Postgres1→2 tests, concurrency, security review, and real end-to-end UX. **Schema version downgrade is not safe simply by reverting source**: restore from verified pre-migration backup or forward-migrate. S-06.02.23 remains the sole IN_PROGRESS review.


## 2026-10-15 — Qualified reply conversion, Contact 360 and human priority queue

On develop only, source-level product features F-06.13, F-06.14 and F-06.15 are prepared and IN_REVIEW. Existing Reply Inbox, Human Follow-ups and Sales Tracker were inspected first; no parallel lead database or unauthorised provider action was created.

- F-06.13: explicit positive/meeting reply promotion reuses one existing matching sales lead or creates one, with campaign membership relation and event within one transaction, idempotency, ambiguous lead rejection and unchanged send stops.
- F-06.14: protected Contact 360 overview of campaign identity, message counts, latest reply metadata, triage, next human task and existing sales lead, with response allowlists; integrated across operator screens.
- F-06.15: read-only selected-campaign priorities from overdue open tasks, unreviewed replies and linked untouched/stale opportunities; deterministic SQL filtering/pagination and navigation.

New outreach/relationship_ops.py, frontend Contact360.tsx and ActionCenter.tsx, protected API endpoints and UI integrations. CRM SQLite schema 11; PostgreSQL schema step 3; sales-link table included in CRM_TABLES backup inventory. Test source tests/test_relationship_intelligence.py and frontend/src/pages/RelationshipIntelligence.test.tsx; legacy CRM table count now 34. All docs/evidence/2026-10-15-three-relationship-features.md gates still required, especially disposable real PostgreSQL migration, backup/restore, concurrency, full pytest/TypeScript build, Chrome UI and Q-27 workspace authorisation review.

Do not claim verified, deployed, or DONE. A code-only downgrade of a migrated schema is unsafe. Original send path unmodified; previous S-06.02.23 audit remains IN_PROGRESS.


## 2026-10-15 — Cross-campaign Search, Account Intelligence, Revenue Attribution

Feature-level work chosen and implemented in source: F-06.16 Unified CRM Search, F-06.17 Account Intelligence Workspace, F-06.18 Campaign-to-Revenue Attribution. Scope stays `kunalwagh101/off_CRM` / `develop` only. Backend in `offsetx_apollo_builder/outreach/crm_insights.py`, protected read-only endpoints in `api/app.py`, screens `frontend/src/pages/{CRMSearch,AccountIntelligence,RevenueAttribution}.tsx`, routes in `App.tsx`. No writes or schema changes.

Global search is bounded, literal-query escaped and correctly aligns the selected campaign/member. Company accounts are grouped by `lower(trim(company))` with independently counted existing contacts, memberships, tasks and workspace sales leads; not a legal-entity verification. Attribution uses SQL `ROW_NUMBER` over existing human-created campaign-sales links to count each opportunity and its won/booked/cash values at most once, via earliest link. Monetary units aren't converted and association isn't proof of causation.

Test source `tests/test_crm_insights.py`, `frontend/src/pages/CRMIntelligence.test.tsx`; specifications `docs/features/unified-crm-search.md`, `account-intelligence-workspace.md`, `campaign-revenue-attribution.md`, evidence `docs/evidence/2026-10-15-crm-intelligence-three.md`. Real pytest/Ruff/Vitest/frontend build/PostgreSQL/Chromium/tenant review are still required. All three IN_REVIEW, not DONE/deployed; original S-06.02.23 audit remains IN_PROGRESS. Existing unresolved CI runner-allocation and backup/retention/tenant boundaries unaffected; no new database table is added.


## 2026-10-15 — Next three CRM operations product features

Continuation is on `kunalwagh101/off_CRM`, branch `develop` only, from verified HEAD `882915552951807f244bb2b44092d48a65a1c831`. The owner requested three substantial product features. Selected **F-06.19 CRM Data Quality Centre**, **F-06.20 Campaign Comparison Dashboard**, **F-06.21 Follow-up Performance Centre** after inspecting prior CRM Search, Account Intelligence, Attribution, Sales Tracker, contacts, campaign messaging and human task schemas. No already-implemented feature was re-created.

Code: new `offsetx_apollo_builder/outreach/crm_operations.py` implements three read-only SQL services; three authenticated bounded `/crm/quality`, `/crm/compare`, `/crm/followup-performance` GET endpoints in `api/app.py`; `frontend/src/pages/CRMOperations.tsx` provides three navigable operator pages wired in `App.tsx`. All reuse existing stored tables, no schema change or migrations, external send/model/provider calls or new secrets. Backend source `tests/test_crm_operations.py` and Vitest source `frontend/src/pages/CRMOperations.test.tsx` are authored, plus specs `docs/features/crm-data-quality.md`, `campaign-comparison.md`, `followup-performance.md`.

**Verification status: IN_REVIEW**, not DONE, deployed, or runtime-verified. The GitHub Actions run `38674480652` preceding this batch had two failed jobs with **zero steps**; this is not a test result. The current connected GitHub filesystem is not an executable full checkout. Required gates: `uv run ruff check --select E9,F63,F7,F82 .`; `uv run pytest tests/test_crm_operations.py tests/test_crm_insights.py tests/test_relationship_workflows.py tests/test_relationship_intelligence.py -q`; `uv run pytest -q`; `uv run python scripts/verify_board.py`; `cd frontend && npm ci && npm test && npm run build`; disposable PostgreSQL query/performance and browser accessibility/security/role isolation review. Q-27 remains open: contacts/campaigns are install-wide, not per-customer. Do not enable unrelated customer sharing or claim tenant isolation. `S-06.02.23` remains sole IN_PROGRESS story; WIP max 2 unchanged.


## 2026-11-04 — A32 restricted sandbox output repair (F-06.02)

Only `develop`. Production audit S-06.02.23 remains the sole IN_PROGRESS item. The owner asked to continue coding, so test-first S-06.02.64 was prepared under build-ahead with its work order. On test-only code `64af3c5` isolated Render `dep-dblipuff3r2c73a96th0` failed 5 A32 acceptance tests as expected; source `c63fe5c` repaired host permissions without changing container UID or sandbox privileges. Follow-on documentation in `6c62bc6` recorded requirement R-191 and decision DD-143. Source-pinned isolated Render `dep-dbliqluc6qcc73bht1hg` observed 5 focused A32 PASS, SQLite 3,002 PASS / 56 skipped, focused PG 215 PASS, 12 concurrency repetitions, frontend/browser/security/structural verifier PASS. Full disposable PostgreSQL 3,026 PASS/101 skipped and isolated Render review LIVE confirmed at 2026-11-04 13:24:37 UTC on c63fe5c. Native Docker write, independent penetration, full-history verifier and failure reference acceptance remain open; IN_REVIEW, not DONE, no main/customer rollout. See docs/evidence/2026-11-04-a32-sandbox-workspace.md.


## 2026-11-04 — S-06.02.65 / A22 nested video edit input

Branch develop from fd976d2. Owner requested the next feature; production audit S-06.02.23 remained sole IN_PROGRESS, no READY. Selected one partial A22 API write validation story under build-ahead, not DONE. Test-only 86da047 / isolated Render dep-dbln67d6e07s739droo0: 6 expected FAILED/2 passed. Corrected schema/app source 384070d / isolated Render dep-dbln72ff3r2c73e4r2q0: 8 focused PASS; full QA and final LIVE pending at checkpoint. Existing edit engine, save/undo and login unchanged; no schema migrations, real sends or customer data. Requirement R-192, defect D-367, decision DD-144, work order and evidence recorded. Full A22 write-route audit and independent penetration remain OPEN. See docs/evidence/2026-11-04-a22-video-edit-validation.md.


## 2026-11-04 — A22 Unicode validator follow-up (final QA pending)

After the first eight A22 tests passed on 384070d, an independent adversarial reasoning check reproduced a UnicodeEncodeError / HTTP 500 in a minimal FastAPI/Pydantic handler for JSON \uD800 when a validator used ensure_ascii=False and UTF-8 encoding. Follow-up source 1201495 now rejects surrogate characters in video edit parameter names/text and uses escaped ASCII for request byte bounds. Two real off_CRM HTTP regression tests were committed. Final isolated Render run dep-dblnc3tg1s2s73cvcvn0 is underway, targeting 10 A22 tests and full SQLite/PG/browser gates. Previous dep-dbln72ff3r2c73e4r2q0 was superseded and canceled before its full PostgreSQL stage. Do not credit it as LIVE or final code QA. D-368/DD-145. No main/customer deployment.


## 2026-11-04 — S-06.02.65 final isolated Render result

Final review evidence: executable/test source `12014959e82b27c4fce65cc4f5c983c65c28174b`, isolated Render `dep-dblnc3tg1s2s73cvcvn0` **LIVE** on 2026-11-04 at 18:34:14 UTC. A22 focused **10 passed**; full SQLite **3,012 passed, 56 skipped, 44 warnings**; full real disposable PostgreSQL **3,036 passed, 101 skipped, 44 warnings**; focused PG **215 passed**; 12 real repeated concurrency probes PASS. Frontend tests/build/npm audits, Chromium desktop/mobile Contacts/Public Demo, A09 and A18 browser security checks, Ruff, API auth and structural board verifier PASS. Docker board verifier used `--skip-tests`: no historical evidence replay. No independent penetration, actual customer video browser acceptance, full A22 write-API matrix, customer deployment or `main` promotion.

Source `1201495` is the final code/test revision; documentation followed on `develop`. Only isolated review marker was deployed, not the customer/public/demo service. The existing audit S-06.02.23 remains IN_PROGRESS, S-06.02.65 IN_REVIEW, and no additional work is authorised on main. Complete A22 route fuzzing, independent penetration, full-history verifier and customer video browser acceptance remain open.
