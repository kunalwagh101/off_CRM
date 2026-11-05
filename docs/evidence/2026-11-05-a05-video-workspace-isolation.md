# A05 / S-06.02.68 — Cross-workspace video resource ownership

## Exact scope
Develop only. Existing VideoStore records already carry workspace_id for video projects, imported recordings, renders and reviews. A workspace's authenticated VideoEditorEngine gets its workspace_id from the session. But individual project/media/render reads and SQL lists ignored stored ownership, so a workspace account could obtain another account's video or change its project if it knew an ID. CRM campaign tenant ownership is intentionally **not** decided (Q-27), and a shared campaign cannot grant authority over every video row.

## TDD RED on isolated Render
- Test source `95cfb3cb2b8b3654d97d6ebe6e87d1c21122ac71`, initial early Docker review source `d22d3a8af34e46f999d4c04a1830da13598832d8`, isolated Render `dep-dbm4isu1egvs73bau35g`.
- `uv run pytest -q tests/test_audit_a05_video_workspace_isolation.py`: **4 expected failures** under two real authenticated workspaces sharing one synthetic campaign, with imported media and render bytes. No production data.
- Initial code at `77307a8` (SQL owner filters), `9300330` (engine-owned record checks) and `de92a5a` (download gates); intermediate isolated Render `dep-dbm4khbm8hqs73encvo0`: **3 passed/1 failed**. The remaining failure exposed undo's broad LookupError handler converting the correctly refused foreign KeyError into 409 Conflict, which could reveal project existence.
- Updated undo/redo error mapping at `a94aedb`; extended test to cover redo, frame, reviews at `246741b8663d56991d169af246dab77681f63648`.

## Security contract
- SQL filtering occurs **before LIMIT** for list_projects, list_media, list_renders, list_reviews and pushed_renders, retaining unscoped defaults for isolated store migration/internal callers. The authenticated video engine always supplies its caller workspace.
- VideoEditorEngine resolves project/media by (ID, workspace_id) before project edits, undo/redo, renders, history, review decisions, media placement, transcription and assembly. Foreign IDs act like missing IDs.
- The direct media and render download API routes check workspace_id **before resolving paths or serving bytes**. The global 404 behaviour is preserved; undo/redo no longer convert owner refusal to a misleading 409.
- Same-workspace video features, existing schemas and local workspace rows stay supported. Other user content stores and complete CRM campaign tenancy are outside this change.

## Release gates
Exact-source full Render results pending for `246741b8663d56991d169af246dab77681f63648` on isolated QA `dep-dbm4lgrbc2fs738acn6g`; update with observed counts, never assume success. Run full SQLite, disposable PostgreSQL, video/security focused gates, frontend npm/build, Chromium, static checks, repeated concurrency, structural board verifier. Historic DONE tests, independent penetration, real production multi-tenant security and customer release still pending.

References: D-372; DD-148; R-195; A05, S-06.02.23 (IN_PROGRESS); S-06.02.68 (BACKLOG). Only develop, no main/customer service change.

## Exact executable/test-source acceptance on isolated Render

- **Executable/test source** `246741b8663d56991d169af246dab77681f63648`; isolated review runner `dep-dbm4lgrbc2fs738acn6g`, autoDeploy off. Subsequent repository commits are documentation only.
- Focused A05 real API cookie-session regression: `uv run pytest -q tests/test_audit_a05_video_workspace_isolation.py` **4 PASSED, 1 Starlette deprecation warning** (Docker step #27). Verified foreign direct downloads, edit/delete/undo/redo/history/frames/reviews access, scoped campaign project/media lists and summary, queue hiding and refusal to transcribe/place another workspace's audio. Synthetic files only.
- Full SQLite `uv run pytest -q`: **3,036 passed, 57 skipped, 44 warnings** (step #62).
- Focused disposable PostgreSQL integration suite: **215 passed**, plus three individual hosted storage probes passed. Full real disposable PostgreSQL `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`: **3,061 passed, 101 skipped, 44 warnings** (step #65), including the new real API A05 tests.
- Configured Ruff, API/AI/security focused tests, frontend `npm ci`, tests/build and npm audits, real Chromium A09/A18, desktop/mobile Contacts and Public Demo, 12 repeated concurrent SQLite writes and board **structural** verifier passed. Structural board verifier uses `--skip-tests`; no full Git-history DONE evidence replay is claimed.
- The Render QA service is a build/test marker, not the production web application. Its LIVE status is tracked separately; successful tests alone do not prove actual customer deployment. No real customer media, provider call or mail send was exercised.
- A05 broader user/role/CRM data authorisation remains IN_PROGRESS, Q-27 campaign tenancy and independent penetration/customer acceptance remain open. S-06.02.68 remains BACKLOG; no main/customer deployment.
