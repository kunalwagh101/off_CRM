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
