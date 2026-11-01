# S-06.02.54: restore AI in the demo

Owner correction: AI orchestration is central; disabling it was not requested. Work on develop only, base 269728567222c3098a0c9ecd92bb91cccbfcdcfe. Public service srv-dbj5q5vb9u1s73d4fe1g; original srv-d9d4i8ok1i2s73cv41ig still eb4c820 with auto-deploy off. Render connector used for service operations.

Scope: restore existing Chat, Compare, Plan and Image APIs/UI with provider setup. A verified signed public cookie derives an opaque session AI workspace; keys/chats/logs cannot cross sessions. Logout revokes its cookie and removes only its connected keys. Sample CRM writes, private mailbox, external sending and owner/browser operations remain protected. No fake provider in production and no new model egress path. The existing Plan mode divides text jobs among models; it does not automate every CRM/browser action. Do not claim that missing connection is built.

Local test-first RED: four cases in tests/test_public_demo_ai.py failed because shared identities and 403 guards prevented AI. A separate security regression returned 200 for another workspace's egress record, expected 404. An earlier attempted test invocation failed because the recreated virtualenv lacked pytest; that environment failure was not counted as RED. Locked dev/email/postgres extras were then installed.

Initial GREEN command: `uv run --no-sync pytest -q tests/test_public_demo_ai.py tests/test_public_demo.py tests/test_public_demo_entrypoint.py tests/test_api_auth.py tests/test_ai_modes.py tests/test_workspace_isolation.py`: 75 passed in 19.34s. The orchestration integration case uses an explicit provider test double and observes one planner call plus two worker calls through the real broker; it is not evidence of a live vendor/model. Frontend and final assertions still being verified.

Original deployment blocker: secure CRM login for backup was declined. The Render connector can trigger deploys but has no authenticated CRM backup or existing password-read action. Do not repeat browser login prompts or risk erasing owner state. User asked to continue through the Render connector. Original service remains unchanged until a backup/access or an explicit disposable reset instruction is available. Public visitor installation has no model key; a real model test remains pending, not passed.

Self-review only. Full Render regression, real browser acceptance, actual vendor response and original deployment upgrade are recorded separately when observed. IN_REVIEW, not a production or arbitrary automation completion claim.
