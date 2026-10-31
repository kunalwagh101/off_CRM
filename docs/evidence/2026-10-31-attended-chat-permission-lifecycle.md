# F-06.01 / S-06.01.02 — chat ownership and temporary owner browser grants

**Branch:** `develop` only. This is a backend slice of an existing IN_REVIEW story, not a new DONE claim.

## Why this change is needed

The AI Copilot chat routes previously omitted workspace_id and defaulted to
`local`. `list_messages` queried by chat ID alone, and `send_message`
stored a user turn without checking workspace ownership. An authenticated
member could therefore interact with a local-owner chat and risk private
history entering the AI responder. The existing `ChatPermissionGrants` class
was not accessible through authenticated owner approval or chat deletion.

## Actual RED on Render

- Source commit `43a5d147e951351b36d61581e1c399cf315cf390`.
- Isolated review deploy `dep-dbiqkes9v7es738bb040` **build_failed** at
  `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`.
- **3 failed, 26 passed, 1 warning**. Newly added tests covered cross-workspace
  chat API access, grant approval/closure and restart lifetime.

## Code changes

- `outreach/ai_chat.py` now checks chat ownership before message insertion,
  before giving turns to the responder, and on message/history reads; project
  attachment and movement must stay within the same workspace.
- All `api/app.py` AI chat and project routes pass the authenticated workspace.
  Foreign chat reads, edits and deletes return 404, not leaked content or success.
- Owner explicit `POST /api/v1/ai/chats/{chat_id}/permissions` uses a strict
  `AttendedChatGrant` request. The tool must already be in policy mode `ask`,
  and global or per-tool `deny` cannot be elevated.
- Authenticated `GET` gives scoped active granted tools; owner `DELETE`
  clears them. Deleting the conversation also closes its grants.
- `ChatPermissionRegistry` uses memory only, keys by workspace and chat, caps
  active sessions and expires grants within one hour. Restart loses all grants.

## Test refinement and latest review candidate

- First implementation at `d3978d8`: Render deploy
  `dep-dbiqlkajnfac73bc10vg` **build_failed**, **2 failed, 29 passed**.
  One test accidentally closed a shared app lifespan by entering a second
  TestClient context, and a second tried to approve an already-allow tool
  (correctly 409). These were test setup errors, not waived backend defects.
- Tests corrected in candidate `a4e08558683c8be0ae4de8c615b7c736cbfe0b4c`.
  Review `dep-dbiqmb142hec73b8c12g` passed **31 targeted** agent
  and permission tests. The final code `35881993a267a4c261348d61edc83adb4cfdf6b1`
  adds shutdown and runtime-restore grant invalidation. Isolated review
  `dep-dbiqn77b9u1s73c8pp80` confirmed:
  - `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`:
    **32 passed, 1 warning**.
  - `uv run pytest -q tests/test_hosted_storage_readiness.py`:
    **7 passed**.
  - API typed-body contract **1 passed**, operational health **7 passed**.
  - Full SQLite/PostgreSQL, frontend/npm and Chromium stages are separate
    checks; do not infer those results from the targeted pass.

## Remaining product and security gates

This does NOT yet connect an authenticated attended browser-agent execution
endpoint to `AgentRun(chat_permissions=...)`. AI Copilot chat still exposes
text through the guarded egress broker, not browser tool execution. No
customer-facing approval UI is included (frontend renovation is separate).
The in-memory registry is not shared across multiple web replicas by design.
No live external penetration test, full Git-history verifier, or production
restart/multi-instance acceptance is claimed. D-330 (lost settings default allow),
upstream S-04.01.01, and review of other agent adapters stay open.
No production or `main` deployment.
