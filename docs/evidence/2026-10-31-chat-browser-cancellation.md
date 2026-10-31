# F-06.01: owner cancellation for in-flight read-oriented chat browser runs

**Branch:** `develop` only. **Scope:** backend cancellation of a synchronous HTTP browser read that already uses the existing isolated `RoutineAgentExecutor`. **Not a new attended interactive UI or production release.**

## Problem and security contract

An owner who POSTs `/api/v1/ai/chats/{chat_id}/browser-runs` previously had to wait until the run finished or hit the server's 115-second timeout. There was no API to observe the active request or stop it. A timed-out/canceled run must release the database-backed workspace browser lease and terminate the underlying browser runner; a success response without task cancellation would mislead the owner.

## Implementation

- `agent/active_runs.py`: a bounded-by-workspace-lease, non-durable registry of active asyncio tasks, keyed by workspace and chat. Each run has a random opaque ID, its owning event loop and task. Status reveals only the matching workspace/chat's ID. A cancellation is scheduled safely on that run's event loop; a false/no-longer-active ID returns not found. Closing the registry on shutdown/restore cancels outstanding tasks. No model-generated text can call these owner-only endpoints.
- `GET /api/v1/ai/chats/{chat_id}/browser-runs`: owner-only view of current run or `{"active":false}`.
- `DELETE /api/v1/ai/chats/{chat_id}/browser-runs/{run_id}`: owner-only, 202 means **cancellation requested**, not completed. A different tenant/chat/run ID cannot stop the task. Browser-run POST responds with a `cancelled` outcome once the underlying task actually raises `CancelledError` and has completed cleanup; the original request finally block releases the workspace lease.
- Deleting the chat, runtime restoration or application shutdown cancels active tasks. The registry is explicitly listed in the runtime close order and in the non-durable storage inventory.
- Existing browser guards remain: only public URLs; strict current workspace policy, chat-grant checks, read-oriented deny for click/type/press/select and **unattended-only** domain rules until real monitoring exists. No new egress bypass or database schema change.

## Render TDD evidence

- **RED source:** `cf31c149515f598538f789f49afd4185c1d121c2`, review `dep-dbiugrm7bikc73dtnrr0`, build **FAILED** at the early `uv run pytest -q tests/test_agent_permissions.py tests/test_agent_run.py` gate. Actual result: **3 failed / 40 passed / 1 warning**. The 3 new tests covered scoped cancellation registry, owner cancellation/lease release, and unauthorised member access. This was an expected failing test-first check.
- **Candidate source:** `fd8a73ae4a13eb1e04aaf2f59a970050883df806`, review `dep-dbiuigg473hc73ambq30`. The code commits preceding it were `b99b4a9` (task registry), `4878d1d` (API/status/cleanup), `883d670` (storage inventory). A fourth new test checks shutdown cancellation.
- **GREEN evidence:** Pending final Render result. No passing claim is made until the matching logs are inspected.

## Release blockers

The feature remains within **S-06.01.02 IN_REVIEW**. This allows cancellation via owner API, not a browser watch-and-cancel UI; it has no progress stream, persistent status, cross-process cancellation transport, or verified real external Docker/browser session. Since tasks live in one process, cancellation endpoints cannot act across multiple web instances. Production DNS-rebinding/egress firewall, restart acceptance, D-330 missing-settings default allow, upstream S-04.01.01, independent penetration and full-history board verification remain unresolved. The review service uses synthetic tasks and tests; it is not production.

**Rollback:** remove the cancellation routes and active-run registration, keep existing safe read-oriented policy and the pre-existing 115-second HTTP timeout; no database migration is involved.
