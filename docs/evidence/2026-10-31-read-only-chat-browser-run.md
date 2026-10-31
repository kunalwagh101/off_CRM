# F-06.01 / S-06.01.02 — Owner-initiated read-oriented browser run

**Branch:** `develop` only. **Application source for final QA:** `3150fbb0de3a20e7f58f2ddcd59700353677fb0f`. This is an IN_REVIEW backend slice, not a customer-ready attended browser agent.

## User contract and security decision

An authenticated install owner can POST a bounded request to
`/api/v1/ai/chats/{chat_id}/browser-runs` with an existing owned chat,
`goal` (1–4,000 chars), public absolute HTTP(S) `target_url` (10–2,048 chars)
and `step_budget` (1–5). It performs a strict owner/chat check, rejects
local/private/metadata URLs, malformed URLs and embedded URL credentials,
fetches the latest strict workspace browser policy, requires `goto` to be
allowed (by policy or a live chat-scoped grant), and acquires the same
workspace lease used by scheduled routines. A busy workspace returns 409
without launching another browser.

The real `RoutineAgentExecutor` is called with a chat-specific grant
object and executes `AgentRun` using the original broker and isolated
`BrowserBox` path. The policy is re-read before navigation and every chosen
action. HTTP requests have no live visual supervision, stop control or
step-by-step approval. Therefore the run stays **read-oriented, not fully
attended**: a separate immutable effective policy denies `click`, `type`,
`press` and `select` regardless of chat grants, and the existing
**unattended domain policy** is enforced for both initial URL and browser
network activity. Sites requiring a watched browser session (for example
LinkedIn) are refused. The real code still permits `goto`, `read`,
`screenshot`, `scroll`, `wait_for`, and `back`; a GET URL can have
side effects, so this is not a general no-side-effects proof.

The request uses a 115-second execution timeout, 180-second workspace
lease, maximum 5 model decisions, 90-second measured latency ceiling and
$0.25 per-request provider spending limit. A failed run returns a
secret-safe error reference and releases the workspace lease. Browser
startup/exit already uses the runner's Docker cleanup. The outcome returns
its run id and structured trace summary. There is no new storage schema,
provider import path or persistent chat-approval record.

## Actual TDD RED evidence

1. Source `f92a3e5bf1b7f314f36a623063549371cbb87545`;
   isolated Render `dep-dbisfo67bikc73dohamg`, **build_failed**.
   `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`:
   **4 failed, 33 passed, 1 warning**. The new tests required the
   authenticated run route, read-only policy, approved goto and shared
   workspace lease, none of which existed.
2. A code-review security finding D-335: the initial implementation used
   `unattended=False` for HTTP runs, despite no live watching/cancellation.
   Source `b6cc20e955372e7ef804ed845170c59d40c7f311`, isolated Render
   `dep-dbisj1ks728c7386u920`, **build_failed** with
   **1 failed, 36 passed, 1 warning**. The new case required refusing
   attended-only sites. Corrected source applies `unattended=True` to
   API preflight, BrowserBox and Page regardless of owner grant.

## GREEN review

- First code `08c6380750563fbd9210011150a1d24a8c3ddb7e`: targeted
  **37 passed** on `dep-dbish8o473hc73ahe7r0`; broader QA was not a
  release claim and the D-335 follow-up required correction.
- Final code `3150fbb0de3a20e7f58f2ddcd59700353677fb0f`,
  isolated Render review `dep-dbiskimc6qcc739ivrcg`:
  - `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py`:
    **40 passed, 1 warning**.
  - Runtime inventory/close-order cases: **2 passed**; API typed-body contract
    **1 passed**; hosted readiness **7 passed**; operational health **7 passed**.
  - Full SQLite `uv run pytest -q`: **2824 passed, 45 skipped,
    44 warnings**.
  - Focused disposable PostgreSQL: **215 passed, 1 warning**.
  - Full disposable PostgreSQL `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q`:
    **2844 passed, 94 skipped, 44 warnings**.
  - Board-verifier unit cases **67 passed**, Ruff syntax/severity gate passed,
    browser Chromium Contacts synthetic 1280px and 390px **PASS**.
  - Frontend build and audit checks were part of the reviewed Docker build.
  - Render `LIVE` review status must be confirmed separately; a completed
    test stage does not prove a running service.
  - Additional tests cover owner/member scope, internal and attended-only
    destinations, invalid URL parsing, failure references, lease cleanup,
    and the executor's goto preflight.
- No real external provider/Docker browser execution was performed on the
  isolated Render test runner. The actual browser session, DNS rebinding
  firewall and owner-supervised experience require distinct live acceptance.

## Remaining release blockers

`S-06.01.02` stays IN_REVIEW. A customer-facing live watch/cancel UI,
real attended social site access, independent penetration (including DNS
rebinding), real external browser/provider smoke test, cross-process lease
and chat-grant semantics, D-330 lost-settings default allow, upstream
`S-04.01.01`, full Git-history verifier and durable trace/production
storage signoff remain open. The existing free Render review image and
its synthetic tests do not establish production acceptance. No `main`
promotion or customer production deploy was done.

**Rollback:** revert the HTTP route and `attended` variant of executor;
the established scheduled routine contract remains unchanged. Never
remove the unconditional read-oriented denies or domain restrictions
without a real monitored/cancellable user session.
