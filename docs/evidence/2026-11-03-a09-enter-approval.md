# A09 / S-06.02.57 — keyboard approval bypass

Date 2026-11-03. Branch develop only. S-06.02.23 is the active production audit; this remediation is an independent owner-authorised story, not the complete audit or F-06.02.

## Threat and reproduction
`Page.press('Enter')` dispatches real Chrome keyDown/keyUp. The earlier `_WHAT_ENTER_WOULD_DO` DOM probe considers textareas, contenteditable, form-less input and unknown foreign-language labels harmless; however page JavaScript may attach a document-level Enter listener that causes an external effect. An AI model cannot grant human approval.

TDD **RED**: test-only `dfe6b788fa28a168a2de4684070b0944ff731c8e` in isolated Render review `dep-dbkpkiek1f9s73dllh50`. Early `uv run pytest -q tests/test_browser_agent.py -k A09_enter_unknown_focus` returned **4 failed, 67 deselected** (2.17s); each failure states `AssertionError: An unapproved Enter event reached the page`. Build correctly failed at this gate.

## Fix and test matrix
The existing shared `Page._clear_to_act` gate is reused. If a focused Enter has an unrecognised label or role, it is treated as `submit` rather than a harmless `click`. Thus no key dispatch occurs before explicit trusted approval. Navigation-key flow and controlled approval remain unchanged.

`tests/test_browser_agent.py` holds four adversarial mock-CDP probes and four real Chromium custom-handler scenarios: textarea, rich editor, form-less input, non-English button. A fake CDP success is not sufficient; Chromium must show `UNSENT` after unapproved Enter and `SUBMITTED` after trusted owner confirmation.

## Known limits and rollback
This change may ask approval for innocent Enter actions. Custom JavaScript action intent cannot safely be inferred from DOM labels. This does **not** establish an effect-bound approval token, prevent arbitrary click/Space bypass or certify DOM-change/navigation invalidation, external security penetration, or real provider/customer browser sessions. Controlled local HTML does not send anything to a third party. Rollback reopens D-358 and is unsafe without equivalent replacement protection; no database/schema migration or customer content involved.

## Verification
GREEN and full final QA unverified at this checkpoint. Render does not auto-deploy: explicitly trigger pinned test service, inspect tested commit, logs and terminal LIVE marker. Full historical board-verifier replay and independent penetration must be recorded separately.

## Full-suite test-contract regression (D-359)

The first GREEN-source full SQLite run on Render `dep-dbkpn83bc2fs73a1hljg` showed five `F` markers at approximately 40% while the suite continued. Existing `tests/test_browser_enter_gate.py` had five assumptions that an ordinary or unfocused Enter cannot cause a side effect. Those assumptions contradict the controlled page JavaScript exploit and cannot remain security requirements. Updated them to require approval, retaining a real explicitly approved Enter dispatch test and independent non-effectful-key tests. Added an early gate for that entire legacy test file and an explicit model-argument rejection test for `press(confirmed=true)`. A new exact-code build is required. Final first-suite summary and corrected suite outcomes must be recorded from Render logs before marking this story IN_REVIEW.

## 2026-11-03 — final exact-code isolated QA and review status

**Implementation/test source:** `065c31001ae9042d4bde7472aa8dcd1bcdd263ac`. **Render review service:** `srv-db86p4u89jmc73cehns0` in workspace `tea-cspt7hggph6c739lq5j0`. **Deploy:** `dep-dbkps0m7bikc73fil3vg`, completed **LIVE** at **08:59:44 UTC**. Render's LIVE marker belongs to the isolated Docker QA runner, **not** the customer service or `main`.

| Test/check | Observed result |
|---|---|
| Original TDD RED, test-only dfe6b78, `dep-dbkpkiek1f9s73dllh50` | 4 FAILED, 67 deselected — unapproved key dispatched |
| First patched build 0fef11d, `dep-dbkpn83bc2fs73a1hljg` | A09 focused 4 PASS; full SQLite **5 FAILED, 2949 passed, 54 skipped** due to five unsafe legacy test assumptions, logged as D-359 |
| Final `uv run pytest -q tests/test_browser_agent.py -k A09_enter_unknown_focus` | **4 passed**, 67 deselected |
| Final `uv run pytest -q tests/test_browser_enter_gate.py` | **34 passed** |
| Final `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py` | **44 passed**, including model-supplied `press(confirmed=true)` rejection |
| Final full `uv run pytest -q` (SQLite) | **2954 passed, 54 skipped, 44 warnings** |
| Final real Chrome `uv run pytest -q tests/test_browser_agent.py -k A09_enter_js_handler` | **4 passed**, 67 deselected; controlled page remains UNSENT until trusted confirmation |
| Additional real Chromium A18 and desktop/mobile Contacts and visitor demo | A18 **2 passed**; desktop/mobile flows PASS |
| Real disposable PostgreSQL focused gate | **215 passed** |
| Real disposable PostgreSQL full suite (`OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`) | **2977 passed, 100 skipped, 44 warnings** |
| Repeated concurrent CRM writes | **12/12 passed** |
| Static Ruff, frontend unit/build, npm security audits, verifier unit, structural board check `--skip-tests` | Passed as mandatory Dockerfile.review build stages |

The verified Render Docker image was constructed with the passing SQLite, real PostgreSQL and Chrome stages. The final code does not provide any new endpoint, database store, arbitrary model verb, secret access or external network call. No live customer action was triggered during tests.

**Disposition:** `S-06.02.57` → **IN_REVIEW**, not DONE. The A09 historical finding is closed only for the observed Enter-key bypass. Remaining gates: independent live penetration of action-bound approval after navigation and DOM change; broader click/Space/custom control effects; real customer browser/session path; full-history `uv run python scripts/verify_board.py` (the Docker structural `--skip-tests` check did **not** rerun every historical command); and operator production acceptance. S-06.02.23 production audit stays IN_PROGRESS. No `main` or customer deployment.

**Rollback:** A revert alone would reintroduce the demonstrated Enter bypass, so rollback is unsafe until a verified substitute approval boundary is deployed. No state migration or data copy is needed. Document-only review/handoff commit follows the exact tested source and does not change its runtime behaviour.
